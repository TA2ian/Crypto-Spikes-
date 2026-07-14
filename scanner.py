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
import time
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


def analyze_symbol(symbol: str, df: pd.DataFrame) -> list[dict]:
    """فحص شروط الدخول الأساسية + إرفاق طبقة التحليل الإضافية الشاملة"""
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


def main():
    print(f"بدء الفحص لعدد {len(WATCHLIST)} عملة...")
    total_signals = 0

    for symbol in WATCHLIST:
        df = fetch_klines(symbol)
        if df is None:
            continue

        try:
            signals = analyze_symbol(symbol, df)
        except Exception as e:
            print(f"[خطأ تحليل] {symbol}: {e}")
            continue

        for sig in signals:
            msg = format_message(sig)
            send_telegram_message(msg)
            total_signals += 1

        time.sleep(0.3)

    print(f"انتهى الفحص. عدد الإشارات المُرسلة: {total_signals}")


if __name__ == "__main__":
    main()
