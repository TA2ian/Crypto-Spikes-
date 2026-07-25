"""
ماسح العملات الحلال - السكربت الرئيسي الموحد
يقوم بجلب البيانات، الفحص الفني، إدارة نظام النقاط التراكمي،
وإرسال التنبيهات وتحديث بيانات Telegram Mini App.
"""
import os
import json
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
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
CANDLE_LIMIT = 80            # تغطية النماذج السعرية الأطول

RESISTANCE_LOOKBACK = 20
SUPPORT_LOOKBACK = 20
VOLUME_MULTIPLIER = 1.5
RSI_OVERSOLD = 35
SUPPORT_TOLERANCE = 0.005

DIVERGENCE_VOLUME_MULTIPLIER = 2.0  # حد شمعة الفوليوم الضخمة لتأكيد الدايفرجنس

# --- سويتشات تفعيل الطبقات المعلوماتية ---
SHOW_DIVERGENCE = True
SHOW_FIBONACCI = True
SHOW_CHART_PATTERNS = True
SHOW_CVD = True

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

DOCS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "docs")
SIGNALS_JSON_PATH = os.path.join(DOCS_DIR, "signals.json")
CONFIG_JSON_PATH = os.path.join(DOCS_DIR, "config.json")


def fetch_klines(symbol: str, timeframe: str = TIMEFRAME) -> pd.DataFrame | None:
    """جلب بيانات الشموع من KuCoin (عام، بدون مفتاح API)"""
    params = {"symbol": symbol, "type": timeframe}
    try:
        resp = requests.get(KUCOIN_KLINE_URL, params=params, timeout=12)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"[خطأ] فشل جلب بيانات {symbol} ({timeframe}): {e}")
        return None

    if data.get("code") != "200000" or not data.get("data"):
        return None

    rows = data["data"][::-1]
    df = pd.DataFrame(
        rows,
        columns=["time", "open", "close", "high", "low", "volume", "turnover"],
    )
    for col in ["open", "close", "high", "low", "volume"]:
        df[col] = df[col].astype(float)

    return df.tail(CANDLE_LIMIT).reset_index(drop=True)


def is_volume_confirmed(df: pd.DataFrame, index: int = -2, multiplier: float = 1.3) -> bool:
    """تتحقق من أن حجم التداول أعلى من المتوسط قبل اعتماد النمط"""
    if "volume" not in df.columns or len(df) < 20:
        return True
        
    avg_vol = df["volume"].iloc[-20:-2].mean()
    candle_volume = df["volume"].iloc[index]
    return candle_volume >= (avg_vol * multiplier)


def build_extra_analysis(df: pd.DataFrame, rsi: pd.Series) -> dict:
    """يجمع كل نتائج الطبقات المعلوماتية الإضافية مع حماية معالجة الأخطاء"""
    extra = {}

    if SHOW_DIVERGENCE:
        try:
            extra["divergence"] = analyze_divergence(
                df, rsi, volume_multiplier=DIVERGENCE_VOLUME_MULTIPLIER
            )
        except Exception as e:
            print(f"[تحذير] خطأ في حساب الدايفرجنس: {e}")

    if SHOW_FIBONACCI:
        try:
            extra["fibonacci"] = analyze_fibonacci(df, lookback=30)
        except Exception as e:
            print(f"[تحذير] خطأ في حساب فيبوناتشي: {e}")

    if SHOW_CHART_PATTERNS:
        try:
            extra["chart_patterns"] = detect_all_patterns(df)
        except Exception as e:
            print(f"[تحذير] خطأ في كشف النماذج السعرية: {e}")

    if SHOW_CVD:
        try:
            extra["cvd"] = analyze_cvd(df)
        except Exception as e:
            print(f"[تحذير] خطأ في حساب CVD: {e}")

    return extra


def format_extra_lines(extra: dict) -> list[str]:
    """يحوّل نتائج التحليل الإضافي إلى أسطر نصية محددة"""
    lines = []

    # --- دايفرجنس ---
    div = extra.get("divergence")
    if div and (div.get("rsi") or div.get("macd")):
        vol_tag = " + فوليوم ضخم ✅" if div.get("volume_spike") else " (بدون تأكيد فوليوم)"
        parts = []
        if div.get("rsi"):
            label = "🟢 إيجابي" if div["rsi"] == "bullish" else "🔴 سلبي"
            parts.append(f"RSI: {label}")
        if div.get("macd"):
            label = "🟢 إيجابي" if div["macd"] == "bullish" else "🔴 سلبي"
            parts.append(f"MACD: {label}")
        lines.append("📐 <b>دايفرجنس:</b> " + " | ".join(parts) + vol_tag)

    # --- CVD ---
    cvd = extra.get("cvd")
    if cvd:
        if cvd.get("trend") and cvd["trend"] != "غير محدد":
            lines.append(f"💧 <b>CVD تقريبي:</b> {cvd['trend']}")
        if cvd.get("divergence"):
            label = "إيجابي 🟢" if cvd["divergence"] == "bullish" else "سلبي 🔴"
            lines.append(f"💧 <b>دايفرجنس CVD:</b> {label}")

    # --- فيبوناتشي ---
    fib = extra.get("fibonacci")
    if fib:
        if fib.get("near_retracement"):
            ratio, level = fib["near_retracement"]
            lines.append(f"🌀 <b>تصحيح فيبوناتشي:</b> {ratio} ({level:.4f}$)")
        if fib.get("near_extension"):
            ratio, level = fib["near_extension"]
            lines.append(f"🌀 <b>امتداد فيبوناتشي:</b> {ratio} ({level:.4f}$)")

    # --- النماذج السعرية ---
    patterns = extra.get("chart_patterns")
    if patterns:
        found = []
        for key in ["double_pattern", "head_shoulders", "triangle", "channel", "flag"]:
            if patterns.get(key):
                found.append(patterns[key])
        if found:
            lines.append("📊 <b>نماذج سعرية:</b> " + "، ".join(found))
        if patterns.get("trend") and patterns["trend"] != "غير محدد":
            lines.append(f"📈 <b>الاتجاه العام:</b> {patterns['trend']}")

    return lines


def analyze_symbol(symbol: str, df: pd.DataFrame, score_state: dict = None) -> list[dict]:
    """فحص شروط الدخول الأساسية بناءً على الشمعة المكتملة الموثوقة"""
    signals = []

    if df is None or len(df) < max(RESISTANCE_LOOKBACK, SUPPORT_LOOKBACK) + 5:
        return signals

    # الاعتماد على الشمعة المكتملة السابقة لضمان الدقة
    closed_df = df.iloc[:-1]
    last_row = closed_df.iloc[-1]
    
    last_close = float(last_row["close"])
    last_volume = float(last_row["volume"])

    support, resistance = find_support_resistance(closed_df, RESISTANCE_LOOKBACK)
    avg_vol = avg_volume(closed_df, 20)
    rsi = calc_rsi(closed_df["close"], 14)
    last_rsi = float(rsi.iloc[-1])

    candle_patterns = detect_candle_patterns(closed_df)
    bull_ob = find_bullish_order_block(closed_df)
    bear_ob = find_bearish_order_block(closed_df)
    near_bull_ob = price_near_zone(last_close, bull_ob)
    near_bear_ob = price_near_zone(last_close, bear_ob)

    bullish_pattern_names = {"مطرقة (ارتداد صعودي)", "ابتلاع صعودي"}
    has_bullish_pattern = any(p in bullish_pattern_names for p in candle_patterns)

    def confluence_note() -> list[str]:
        notes = []
        if has_bullish_pattern:
            notes.append("نمط شمعة صعودي")
        if near_bull_ob:
            notes.append("قرب Order Block صعودي")
        return notes

    extra_analysis = build_extra_analysis(closed_df, rsi)

    def register_score(reason_prefix: str, direction: str = "bullish", pts: float = 1.0):
        if score_state is None:
            return

        add_points(score_state, symbol, direction, pts, reason_prefix)

        if has_bullish_pattern or near_bull_ob:
            add_points(score_state, symbol, direction, WEIGHTS.get("candle_pattern_confirm", 0.5),
                       f"{reason_prefix} + تأكيد نمط/Order Block")

        div = extra_analysis.get("divergence", {})
        if div.get("rsi") == direction or div.get("macd") == direction:
            add_points(score_state, symbol, direction, WEIGHTS.get("divergence_confirm", 0.5),
                       f"{reason_prefix} + دايفرجنس مؤكد")

        cvd = extra_analysis.get("cvd", {})
        if cvd.get("trend") == "شراء متزايد" and direction == "bullish":
            add_points(score_state, symbol, direction, WEIGHTS.get("cvd_confirm", 0.5),
                       f"{reason_prefix} + CVD شراء متزايد")

    # --- 1. فحص الانفجار السعري وتجاوز الحجم ---
    if avg_vol > 0:
        vol_spike = last_volume / avg_vol
        if vol_spike >= 2.5:
            register_score(f"دخول سيولة عالية (الحجم {vol_spike:.1f}x من المتوسط)", "bullish", 1.5)

    # --- 2. إشارة اختراق المقاومة ---
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
        register_score("اختراق مقاومة", "bullish", WEIGHTS.get("base_signal", 1.0))

    # --- 3. إشارة ارتداد من دعم ---
    is_bullish_candle = last_close > float(last_row["open"])
    near_support = float(last_row["low"]) <= support * (1 + SUPPORT_TOLERANCE)

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
        register_score("ارتداد من دعم", "bullish", WEIGHTS.get("base_signal", 1.0))

    # --- 4. فحص ملامسة مستويات فيبوناتشي الذهبية ---
    fib_res = extra_analysis.get("fibonacci", {})
    if fib_res.get("near_retracement"):
        ratio_str, level_price = fib_res["near_retracement"]
        register_score(f"ملامسة مستوى فيبوناتشي ({ratio_str}) عند {level_price:.4f}$", "bullish", 0.8)

    return signals


def format_message(sig: dict) -> str:
    lines = [
        f"<b>{sig['emoji']} إشارة {sig['type']}</b>",
        f"<b>العملة:</b> {sig['symbol'].replace('-', '/')}",
        f"<b>السعر الحالي:</b> {sig['price']:.4f}$",
        f"<b>المستوى:</b> {sig['level']:.4f}$",
        f"<b>RSI:</b> {sig['rsi']:.1f}",
        f"<b>الحجم:</b> {sig['volume_ratio']:.1f}x المعدل",
    ]

    if sig.get("confluence"):
        lines.append("")
        lines.append("✅ <b>تأكيدات إضافية:</b> " + "، ".join(sig["confluence"]))

    extra_lines = format_extra_lines(sig.get("extra", {}))
    if extra_lines:
        lines.append("")
        lines.append("── <b>تحليل إضافي (طبقة تأكيد)</b> ──")
        lines.extend(extra_lines)

    lines += [
        "",
        "📊 <b>المستويات المقترحة:</b>",
        f"• <b>وقف الخسارة:</b> {sig['stop_loss']:.4f}$",
    ]
    if sig.get("target1"):
        lines.append(f"• <b>هدف 1:</b> {sig['target1']:.4f}$")
    if sig.get("target2"):
        lines.append(f"• <b>هدف 2:</b> {sig['target2']:.4f}$")

    lines.append("\n⚠️ <i>تنبيه آلي استرشادي - راجع الشارت بنفسك قبل اتخاذ القرار</i>")
    return "\n".join(lines)


def send_telegram_message(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[تنبيه] لم يتم تعيين مفاتيح تيليغرام. طباعة الرسالة:")
        print(text)
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }
    try:
        resp = requests.post(url, json=payload, timeout=12)
        resp.raise_for_status()
    except Exception as e:
        print(f"[خطأ] فشل إرسال رسالة تيليغرام: {e}")


def format_mtf_message(mtf_result: dict) -> str:
    direction = mtf_result["direction"]
    is_bullish = direction == "bullish"

    emoji = "🟩" if is_bullish else "🟥"
    direction_label = "إيجابي (صاعد)" if is_bullish else "سلبي (هابط)"
    strength_pct = mtf_result["candle_strength"] * 100

    lines = [
        f"<b>{emoji} إغلاق شمعة {direction_label} — فريم {mtf_result['timeframe_label']}</b>",
        f"<b>العملة:</b> {mtf_result['symbol'].replace('-', '/')}",
        f"<b>سعر الإغلاق:</b> {mtf_result['close_price']:.4f}$",
        f"<b>المستوى المكسور:</b> {mtf_result['level_broken']:.4f}$",
        f"<b>قوة الشمعة:</b> {strength_pct:.0f}%",
    ]

    if mtf_result.get("rsi_divergence_confirms"):
        div_label = "إيجابي" if is_bullish else "سلبي"
        lines.append(f"✅ <b>تأكيد إضافي:</b> دايفرجنس RSI {div_label} متزامن")

    return "\n".join(lines)


def run_multi_timeframe_scan(state: dict, score_state: dict = None) -> int:
    sent = 0
    for symbol in WATCHLIST:
        try:
            results = scan_multi_timeframe(fetch_klines, symbol, TIMEFRAMES)
        except Exception as e:
            print(f"[خطأ فحص متعدد الفريمات] {symbol}: {e}")
            continue

        for res in results:
            candle_time = res.get("candle_time")
            tf = res["timeframe"]

            if candle_time is not None and not is_new_candle(state, symbol, tf, candle_time):
                continue

            msg = format_mtf_message(res)
            send_telegram_message(msg)
            sent += 1

            if candle_time is not None:
                mark_alerted(state, symbol, tf, candle_time)

            if score_state is not None:
                add_points(score_state, symbol, res["direction"], WEIGHTS.get("mtf_candle_close", 1.5),
                           f"إغلاق شمعة {res['timeframe_label']}")

        time.sleep(0.15)

    return sent


def _to_jsonable(obj):
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if hasattr(obj, "item"):
        return obj.item()
    if isinstance(obj, float):
        return round(obj, 6)
    return obj


def write_mini_app_data(all_signals: list[dict]):
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


def check_score_reminders(score_state: dict) -> int:
    sent = 0
    for symbol in WATCHLIST:
        for direction in ("bullish", "bearish"):
            if should_alert(score_state, symbol, direction):
                score = current_score(score_state, symbol, direction)
                breakdown = get_score_breakdown(score_state, symbol, direction)
                
                is_bull = direction == "bullish"
                emoji = "🏆🟢" if is_bull else "🏆🔴"
                lines = [
                    f"<b>{emoji} تذكير تراكمي قوي — {symbol.replace('-', '/')} ({direction.upper()})</b>",
                    f"تجمّعت إشارات متراكمة خلال آخر {WINDOW_HOURS} ساعة",
                    f"<b>مجموع النقاط:</b> {score:.1f} / {SCORE_THRESHOLD}",
                    "\n<b>مصادر النقاط المساهمة:</b>",
                ]
                for event in breakdown[-6:]:
                    lines.append(f"• {event['reason']} (+{event['points']:.1f} p)")

                send_telegram_message("\n".join(lines))
                mark_alert_sent(score_state, symbol, direction)
                sent += 1
    return sent


def process_symbol_worker(symbol: str, score_state: dict):
    """دالة مساعدة لمعالجة العملة بالتوازي"""
    df = fetch_klines(symbol)
    if df is None:
        return []
    try:
        return analyze_symbol(symbol, df, score_state=score_state)
    except Exception as e:
        print(f"[خطأ تحليل] {symbol}: {e}")
        return []


def main():
    print(f"بدء الفحص السريع لعدد {len(WATCHLIST)} عملة...")
    all_signals_for_app = []
    score_state = load_score_state()

    # جلب وتحليل العملات بالتوازي لتسريع التنفيذ
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(process_symbol_worker, sym, score_state) for sym in WATCHLIST]
        for future in futures:
            signals = future.result()
            for sig in signals:
                msg = format_message(sig)
                send_telegram_message(msg)
                all_signals_for_app.append(sig)

    write_mini_app_data(all_signals_for_app)

    # --- فحص متعدد الفريمات ---
    print("بدء فحص إغلاق الشموع متعدد الفريمات...")
    candle_state = load_candle_state()
    mtf_sent = run_multi_timeframe_scan(candle_state, score_state=score_state)
    save_candle_state(candle_state)

    # --- فحص التذكيرات التراكمية ---
    clean_old_events(score_state)
    reminders_sent = check_score_reminders(score_state)
    save_score_state(score_state)

    print(f"انتهى الفحص بنجاح. تم إرسال {len(all_signals_for_app) + mtf_sent + reminders_sent} تنبيهات.")


if __name__ == "__main__":
    main()
