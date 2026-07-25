"""
ماسح العملات الحلال - سكربت مجاني بالكامل
يسحب بيانات KuCoin العامة، يفحص شروط دخول كلاسيكية (اختراق مقاومة/ارتداد دعم)
كإشارات أساسية، ويعرض معها طبقة معلوماتية شاملة:
- أنماط الشموع + Order Blocks
- دايفرجنس RSI وMACD مع تأكيد فوليوم
- مستويات فيبوناتشي (تصحيحي/امتدادي/زمني)
- النماذج السعرية (رأس وكتفين، مثلثات، قاع/قمة مزدوجة، علم، قناة، ترند)

يعمل عبر GitHub Actions كل ساعة (مجاني).
"""
import os
import json
import time
from datetime import datetime, timezone
import requests
import pandas as pd

from coins import WATCHLIST
from indicators import calc_rsi, find_support_resistance, avg_volume
from patterns import (
    detect_candle_patterns,
    find_bullish_order_block,
    find_bearish_order_block,
    price_near_zone,
)
from divergence import analyze_divergence
from fibonacci import analyze_fibonacci
from chart_patterns import detect_all_patterns
from multi_timeframe import scan_multi_timeframe, TIMEFRAMES
from candle_state import (
    load_state as load_candle_state,
    save_state as save_candle_state,
    is_new_candle,
    mark_alerted,
)
from cvd import analyze_cvd
from coin_score import (
    load_state as load_score_state,
    save_state as save_score_state,
    add_points,
    should_alert,
    mark_alert_sent,
    get_score_breakdown,
    current_score,
    clean_old_events,
    WEIGHTS,
    SCORE_THRESHOLD,
    WINDOW_HOURS,
)

# ============ الإعدادات ============
KUCOIN_KLINE_URL = "https://api.kucoin.com/api/v1/market/candles"
TIMEFRAME = "1hour"
CANDLE_LIMIT = 80            # رفعناها من 60 لتغطية النماذج السعرية الأطول

RESISTANCE_LOOKBACK = 20
SUPPORT_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
RSI_OVERSOLD = 35
SUPPORT_TOLERANCE = 0.005

DIVERGENCE_VOLUME_MULTIPLIER = 2.0  # حد شمعة الفوليوم الضخمة لتأكيد الدايفرجنس

# --- سويتشات تفعيل الطبقات المعلوماتية (True = تظهر بالرسالة) ---
SHOW_DIVERGENCE = True
SHOW_FIBONACCI = True
SHOW_CHART_PATTERNS = True

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
SIGNALS_JSON_PATH = os.path.join(DOCS_DIR, "signals.json")
CONFIG_JSON_PATH = os.path.join(DOCS_DIR, "config.json")


def fetch_klines(symbol: str, timeframe: str = TIMEFRAME):
    """جلب بيانات الشموع من KuCoin (عام، بدون مفتاح API)"""
    params = {"symbol": symbol, "type": timeframe}
    try:
        resp = requests.get(KUCOIN_KLINE_URL, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[خطأ] فشل جلب بيانات {symbol}: {e}")
        return None

    if data.get("code") != "200000" or not data.get("data"):
        print(f"[تحذير] لا بيانات لـ {symbol}: {data.get('msg', 'غير معروف')}")
        return None

    rows = data["data"][::-1]
    df = pd.DataFrame(
        rows,
        columns=["time", "open", "close", "high", "low", "volume", "turnover"],
    )
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = df[col].astype(float)

    return df.tail(CANDLE_LIMIT).reset_index(drop=True)


SHOW_CVD = True


def build_extra_analysis(df: pd.DataFrame, rsi: pd.Series) -> dict:
    """يجمع كل نتائج الطبقات المعلوماتية الإضافية بمكان واحد"""
    extra = {}

    if SHOW_DIVERGENCE:
        extra["divergence"] = analyze_divergence(
            df, rsi, volume_multiplier=DIVERGENCE_VOLUME_MULTIPLIER
        )

    if SHOW_FIBONACCI:
        extra["fibonacci"] = analyze_fibonacci(df, lookback=30)

    if SHOW_CHART_PATTERNS:
        extra["chart_patterns"] = detect_all_patterns(df)

    if SHOW_CVD:
        extra["cvd"] = analyze_cvd(df)

    return extra


def format_extra_lines(extra: dict) -> list[str]:
    """يحوّل نتائج التحليل الإضافي إلى أسطر نصية جاهزة للرسالة"""
    lines = []

    # --- دايفرجنس ---
    div = extra.get("divergence")
    if div and (div["rsi"] or div["macd"]):
        vol_tag = " + فوليوم ضخم ✅" if div["volume_spike"] else " (بدون تأكيد فوليوم)"
        parts = []
        if div["rsi"]:
            label = "🟢 إيجابي" if div["rsi"] == "bullish" else "🔴 سلبي"
            parts.append(f"RSI: {label}")
        if div["macd"]:
            label = "🟢 إيجابي" if div["macd"] == "bullish" else "🔴 سلبي"
            parts.append(f"MACD: {label}")
        lines.append("📐 دايفرجنس: " + " | ".join(parts) + vol_tag)

    # --- CVD (ضغط شراء/بيع تقريبي) ---
    cvd = extra.get("cvd")
    if cvd:
        if cvd.get("trend") and cvd["trend"] != "غير محدد":
            lines.append(f"💧 CVD تقريبي: {cvd['trend']} (تقدير غير مباشر، راجع الملاحظة)")
        if cvd.get("divergence"):
            label = "إيجابي 🟢" if cvd["divergence"] == "bullish" else "سلبي 🔴"
            lines.append(f"💧 دايفرجنس CVD: {label}")

    # --- فيبوناتشي ---
    fib = extra.get("fibonacci")
    if fib:
        if fib.get("near_retracement"):
            ratio, level = fib["near_retracement"]
            lines.append(f"🌀 قرب تصحيح فيبوناتشي {ratio} ({level:.4f}$)")
        if fib.get("near_extension"):
            ratio, level = fib["near_extension"]
            lines.append(f"🌀 قرب امتداد فيبوناتشي {ratio} ({level:.4f}$)")

    # --- النماذج السعرية ---
    patterns = extra.get("chart_patterns")
    if patterns:
        found = []
        if patterns.get("double_pattern"):
            found.append(patterns["double_pattern"])
        if patterns.get("head_shoulders"):
            found.append(patterns["head_shoulders"])
        if patterns.get("triangle"):
            found.append(patterns["triangle"])
        if patterns.get("channel"):
            found.append(patterns["channel"])
        if patterns.get("flag"):
            found.append(patterns["flag"])
        if found:
            lines.append("📊 نماذج سعرية: " + "، ".join(found))
        if patterns.get("trend") and patterns["trend"] != "غير محدد":
            lines.append(f"📈 الاتجاه العام: {patterns['trend']}")

    return lines


def analyze_symbol(symbol: str, df: pd.DataFrame, score_state: dict = None) -> list[dict]:
    """فحص شروط الدخول الأساسية + إرفاق طبقة التحليل الإضافية الشاملة
    score_state: إن مُرر، تُسجَّل النقاط تلقائياً بنظام التتبع التراكمي
    """
    signals = []

    if len(df) < max(RESISTANCE_LOOKBACK, SUPPORT_LOOKBACK) + 5:
        return signals

    close = df["close"]
    last_close = close.iloc[-1]
    last_volume = df["volume"].iloc[-1]

    support, resistance = find_support_resistance(df, RESISTANCE_LOOKBACK)
    avg_vol = avg_volume(df, 20)
    rsi = calc_rsi(close, 14)
    last_rsi = rsi.iloc[-1]

    # --- تأكيد أنماط الشموع + Order Blocks (كما كان سابقاً) ---
    candle_patterns = detect_candle_patterns(df)
    bull_ob = find_bullish_order_block(df)
    bear_ob = find_bearish_order_block(df)
    near_bull_ob = price_near_zone(last_close, bull_ob)
    near_bear_ob = price_near_zone(last_close, bear_ob)

    bullish_pattern_names = {"مطرقة (ارتداد صعودي محتمل)", "ابتلاع صعودي"}
    has_bullish_pattern = any(p in bullish_pattern_names for p in candle_patterns)

    def confluence_note() -> list[str]:
        notes = []
        if has_bullish_pattern:
            notes.append("نمط شمعة صعودي")
        if near_bull_ob:
            notes.append("قرب Order Block صعودي")
        return notes

    extra_analysis = build_extra_analysis(df, rsi)

    def register_score(reason_prefix: str):
        """يسجل نقاط الإشارة الأساسية وكل طبقة تأكيد إضافية متحققة"""
        if score_state is None:
            return
        direction = "bullish"  # كلا نوعي الإشارة الأساسية هنا صعوديان بالتصميم الحالي

        add_points(score_state, symbol, direction, WEIGHTS["base_signal"],
                   f"{reason_prefix}")

        if has_bullish_pattern or near_bull_ob:
            add_points(score_state, symbol, direction, WEIGHTS["candle_pattern_confirm"],
                       f"{reason_prefix} + تأكيد نمط/Order Block")

        div = extra_analysis.get("divergence", {})
        if div.get("rsi") == direction or div.get("macd") == direction:
            add_points(score_state, symbol, direction, WEIGHTS["divergence_confirm"],
                       f"{reason_prefix} + دايفرجنس مؤكد")

        cvd = extra_analysis.get("cvd", {})
        if cvd.get("trend") == "شراء متزايد":
            add_points(score_state, symbol, direction, WEIGHTS["cvd_confirm"],
                       f"{reason_prefix} + CVD شراء متزايد")
        if cvd.get("divergence") == direction:
            add_points(score_state, symbol, direction, WEIGHTS["cvd_divergence"],
                       f"{reason_prefix} + دايفرجنس CVD")

    # --- إشارة 1: اختراق مقاومة بحجم ---
    if last_close > resistance and last_volume > avg_vol * VOLUME_MULTIPLIER:
        notes = confluence_note()
        signals.append({
            "type": "اختراق مقاومة",
            "emoji": "🟢🔥" if notes else "🟢",
            "symbol": symbol,
            "price": last_close,
            "level": resistance,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": support,
            "target1": last_close + (last_close - support) * 0.5,
            "target2": last_close + (last_close - support) * 1.0,
            "confluence": notes,
            "extra": extra_analysis,
        })
        register_score("اختراق مقاومة")

    # --- إشارة 2: ارتداد من دعم ---
    prev_open = df["open"].iloc[-1]
    is_bullish_candle = last_close > prev_open
    near_support = df["low"].iloc[-1] <= support * (1 + SUPPORT_TOLERANCE)

    if near_support and is_bullish_candle and last_rsi < RSI_OVERSOLD:
        notes = confluence_note()
        signals.append({
            "type": "ارتداد من دعم",
            "emoji": "🔵🔥" if notes else "🔵",
            "symbol": symbol,
            "price": last_close,
            "level": support,
            "rsi": last_rsi,
            "volume_ratio": last_volume / avg_vol if avg_vol else 0,
            "stop_loss": support * 0.98,
            "target1": resistance,
            "target2": None,
            "confluence": notes,
            "extra": extra_analysis,
        })
        register_score("ارتداد من دعم")

    return signals


def format_message(sig: dict) -> str:
    lines = [
        f"{sig['emoji']} إشارة {sig['type']}",
        f"العملة: {sig['symbol'].replace('-', '/')}",
        f"السعر الحالي: {sig['price']:.4f}$",
        f"المستوى: {sig['level']:.4f}$",
        f"RSI: {sig['rsi']:.1f}",
        f"الحجم: {sig['volume_ratio']:.1f}x المعدل",
    ]

    if sig.get("confluence"):
        lines.append("")
        lines.append("✅ تأكيدات إضافية: " + "، ".join(sig["confluence"]))

    extra_lines = format_extra_lines(sig.get("extra", {}))
    if extra_lines:
        lines.append("")
        lines.append("── تحليل إضافي (معلوماتي، راجعه بنفسك) ──")
        lines.extend(extra_lines)

    lines += [
        "",
        "📊 مستويات مقترحة (راجعها بنفسك قبل الدخول):",
        f"وقف الخسارة: {sig['stop_loss']:.4f}$",
    ]
    if sig.get("target1"):
        lines.append(f"هدف 1: {sig['target1']:.4f}$")
    if sig.get("target2"):
        lines.append(f"هدف 2: {sig['target2']:.4f}$")

    lines.append("")
    lines.append("⚠️ تذكير: هذه تنبيهات آلية وليست توصية، تحقق من القرار بنفسك")
    return "\n".join(lines)


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[خطأ] لم يتم تعيين TELEGRAM_BOT_TOKEN أو TELEGRAM_CHAT_ID")
        print("--- الرسالة التي كانت ستُرسل ---")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        resp = requests.post(url, json=payload, timeout=15)
        resp.raise_for_status()
        print(f"[تم الإرسال] {text[:40]}...")
    except Exception as e:
        print(f"[خطأ] فشل إرسال رسالة تيليغرام: {e}")


def format_mtf_message(mtf_result: dict) -> str:
    """يبني رسالة تيليغرام لإشارة إغلاق شمعة على فريم معين"""
    direction = mtf_result["direction"]
    is_bullish = direction == "bullish"

    emoji = "🟩" if is_bullish else "🟥"
    direction_label = "إيجابي (صاعد)" if is_bullish else "سلبي (هابط)"
    strength_pct = mtf_result["candle_strength"] * 100

    lines = [
        f"{emoji} إغلاق شمعة {direction_label} — فريم {mtf_result['timeframe_label']}",
        f"العملة: {mtf_result['symbol'].replace('-', '/')}",
        f"سعر الإغلاق: {mtf_result['close_price']:.4f}$",
        f"المستوى المكسور: {mtf_result['level_broken']:.4f}$",
        f"قوة الشمعة (حجم الجسم): {strength_pct:.0f}%",
    ]

    if mtf_result.get("rsi_divergence_confirms"):
        div_label = "إيجابي" if is_bullish else "سلبي"
        lines.append(f"✅ تأكيد إضافي: دايفرجنس RSI {div_label} متزامن بنفس الفريم")

    lines.append("")
    lines.append(f"⚠️ تنبيه فريم {mtf_result['timeframe_label']} — راجع باقي الفريمات قبل القرار")

    return "\n".join(lines)


def run_multi_timeframe_scan(state: dict, score_state: dict = None) -> int:
    """يفحص كل عملة على كل الفريمات، يرسل تنبيهات الشموع الجديدة فقط"""
    sent = 0
    for symbol in WATCHLIST:
        try:
            results = scan_multi_timeframe(fetch_klines, symbol, TIMEFRAMES)
        except Exception as e:
            print(f"[خطأ فحص متعدد الفريمات] {symbol}: {e}")
            continue

        new_results = []  # فقط النتائج الجديدة فعلياً (لفحص تطابق الفريمات لاحقاً)

        for res in results:
            candle_time = res.get("candle_time")
            tf = res["timeframe"]

            if candle_time is not None and not is_new_candle(state, symbol, tf, candle_time):
                continue  # نفس الشمعة يلي سبق التنبيه عنها، تخطاها

            msg = format_mtf_message(res)
            send_telegram_message(msg)
            sent += 1
            new_results.append(res)

            if candle_time is not None:
                mark_alerted(state, symbol, tf, candle_time)

            if score_state is not None:
                add_points(score_state, symbol, res["direction"], WEIGHTS["mtf_candle_close"],
                           f"إغلاق شمعة {res['timeframe_label']}")
                if res.get("rsi_divergence_confirms"):
                    add_points(score_state, symbol, res["direction"], WEIGHTS["divergence_confirm"],
                               f"دايفرجنس RSI مؤكد بفريم {res['timeframe_label']}")

        # --- تطابق فريمين أو أكثر بنفس الاتجاه بنفس التشغيلة ---
        if score_state is not None and len(new_results) >= 2:
            directions_count = {}
            for res in new_results:
                directions_count[res["direction"]] = directions_count.get(res["direction"], 0) + 1

            for direction, count in directions_count.items():
                if count >= 2:
                    matched_tfs = [r["timeframe_label"] for r in new_results if r["direction"] == direction]
                    add_points(score_state, symbol, direction, WEIGHTS["mtf_multi_alignment"],
                               f"تطابق فريمات: {', '.join(matched_tfs)}")

        time.sleep(0.2)

    return sent


def _to_jsonable(obj):
    """يحوّل قيم numpy/pandas إلى أنواع بايثون عادية قابلة للتسلسل بـ JSON"""
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "item"):  # numpy scalar (int64, float64...)
        return obj.item()
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def write_mini_app_data(all_signals: list[dict]):
    """يكتب signals.json وconfig.json لمجلد docs/ ليقرأهما الـ Mini App"""
    os.makedirs(DOCS_DIR, exist_ok=True)

    payload = {
        "last_scan": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "signals": _to_jsonable(all_signals),
    }
    with open(SIGNALS_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    config_snapshot = {
        "TIMEFRAME": TIMEFRAME,
        "VOLUME_MULTIPLIER": VOLUME_MULTIPLIER,
        "RSI_OVERSOLD": RSI_OVERSOLD,
        "SHOW_DIVERGENCE": SHOW_DIVERGENCE,
        "SHOW_FIBONACCI": SHOW_FIBONACCI,
        "SHOW_CHART_PATTERNS": SHOW_CHART_PATTERNS,
    }
    with open(CONFIG_JSON_PATH, "w", encoding="utf-8") as f:
        json.dump(config_snapshot, f, ensure_ascii=False, indent=2)

    print(f"[Mini App] كُتبت بيانات {len(all_signals)} إشارة إلى docs/signals.json")


def format_reminder_message(symbol: str, direction: str, score: float,
                              breakdown: list[dict]) -> str:
    """يبني رسالة التذكير عند تجاوز عملة معينة حد النقاط التراكمي"""
    is_bullish = direction == "bullish"
    emoji = "🏆🟢" if is_bullish else "🏆🔴"
    direction_label = "صعودية" if is_bullish else "هبوطية"

    lines = [
        f"{emoji} تذكير تراكمي — {symbol.replace('-', '/')}",
        f"تجمّعت إشارات {direction_label} متعددة خلال آخر {WINDOW_HOURS} ساعة",
        f"مجموع النقاط: {score:.1f} (الحد: {SCORE_THRESHOLD})",
        "",
        "── مصادر النقاط ──",
    ]

    for event in breakdown[-8:]:  # آخر 8 أحداث كحد أقصى لتجنب رسالة طويلة جداً
        lines.append(f"• {event['reason']} (+{event['points']})")

    lines.append("")
    lines.append("⚠️ هذا تجميع آلي لعدد الإشارات ووزنها، وليس توصية — راجع الوضع الحالي بنفسك")

    return "\n".join(lines)


def check_score_reminders(score_state: dict):
    """يفحص كل العملات، يرسل تذكيراً لأي عملة تجاوزت حد النقاط ولم تُنبَّه مؤخراً"""
    sent = 0
    for symbol in WATCHLIST:
        for direction in ("bullish", "bearish"):
            if should_alert(score_state, symbol, direction):
                score = current_score(score_state, symbol, direction)
                breakdown = get_score_breakdown(score_state, symbol, direction)
                msg = format_reminder_message(symbol, direction, score, breakdown)
                send_telegram_message(msg)
                mark_alert_sent(score_state, symbol, direction)
                sent += 1
    return sent


def main():
    print(f"بدء الفحص لعدد {len(WATCHLIST)} عملة...")
    total_signals = 0
    all_signals_for_app = []
    score_state = load_score_state()

    for symbol in WATCHLIST:
        df = fetch_klines(symbol)
        if df is None:
            continue

        try:
            signals = analyze_symbol(symbol, df, score_state=score_state)
        except Exception as e:
            print(f"[خطأ تحليل] {symbol}: {e}")
            continue

        for sig in signals:
            msg = format_message(sig)
            send_telegram_message(msg)
            all_signals_for_app.append(sig)
            total_signals += 1

        time.sleep(0.3)

    write_mini_app_data(all_signals_for_app)

    # --- فحص إغلاق الشموع على عدة فريمات (1h, 4h, 1d, 1w) ---
    print("بدء فحص إغلاق الشموع متعدد الفريمات...")
    candle_state = load_candle_state()
    mtf_sent = run_multi_timeframe_scan(candle_state, score_state=score_state)
    save_candle_state(candle_state)
    print(f"تم إرسال {mtf_sent} تنبيه إغلاق شمعة عبر الفريمات")

    # --- فحص تذكيرات النقاط التراكمية ---
    print("فحص النقاط التراكمية للعملات...")
    clean_old_events(score_state)
    reminders_sent = check_score_reminders(score_state)
    save_score_state(score_state)
    print(f"تم إرسال {reminders_sent} تذكير تراكمي")

    print(f"انتهى الفحص. عدد الإشارات المُرسلة: {total_signals + mtf_sent + reminders_sent}")


if __name__ == "__main__":
    main()
