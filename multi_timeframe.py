"""
فحص إغلاق الشمعة على عدة فريمات (1h, 4h, 1d, 1w)
إشارة إيجابية: شمعة خضراء + إغلاق فوق مستوى مقاومة/قمة سابقة بارزة
إشارة سلبية: شمعة حمراء + إغلاق تحت مستوى دعم/قاع سابق بارز

يُرفق مع كل إشارة تأكيد دايفرجنس RSI إن وُجد متزامناً بنفس الفريم والاتجاه.
"""
import pandas as pd

from indicators import calc_rsi, find_support_resistance
from divergence import detect_divergence

TIMEFRAMES = ["1hour", "4hour", "1day", "1week"]
TIMEFRAME_LABELS = {
    "1hour": "1h",
    "4hour": "4h",
    "1day": "1d",
    "1week": "1w",
}

LEVEL_LOOKBACK = 20   # فترة حساب المستوى (دعم/مقاومة) لكل فريم
MIN_BODY_RATIO = 0.3  # الحد الأدنى لجسم الشمعة كنسبة من مداها لاعتبارها "قوية"


def candle_strength(row) -> float:
    """نسبة جسم الشمعة إلى مداها الكلي (0 = دوجي، 1 = بدون ذيول)"""
    rng = row["high"] - row["low"]
    if rng == 0:
        return 0.0
    return abs(row["close"] - row["open"]) / rng


def check_candle_close(df: pd.DataFrame, timeframe: str):
    """
    يفحص إغلاق آخر شمعة **مقفولة بالكامل** (الشمعة قبل الأخيرة، لأن الأخيرة
    قد تكون لسا قيد التكوّن حسب توقيت الفحص) مقابل مستوى الدعم/المقاومة

    يعيد: dict بالنتيجة أو None إن لم تتحقق أي إشارة
    """
    if len(df) < LEVEL_LOOKBACK + 5:
        return None

    # نستخدم الشمعة قبل الأخيرة كـ"آخر شمعة مقفولة بثقة"
    closed_df = df.iloc[:-1]
    last_closed = closed_df.iloc[-1]

    support, resistance = find_support_resistance(closed_df, LEVEL_LOOKBACK)
    strength = candle_strength(last_closed)
    is_bullish = last_closed["close"] > last_closed["open"]
    is_bearish = last_closed["close"] < last_closed["open"]

    close_price = last_closed["close"]
    candle_time = int(last_closed["time"]) if "time" in last_closed else None

    direction = None
    level_broken = None

    if is_bullish and close_price > resistance:
        direction = "bullish"
        level_broken = resistance
    elif is_bearish and close_price < support:
        direction = "bearish"
        level_broken = support

    if direction is None:
        return None

    # --- تأكيد دايفرجنس RSI بنفس الفريم ---
    rsi = calc_rsi(closed_df["close"], 14)
    rsi_div = detect_divergence(closed_df, rsi)
    rsi_confirms = rsi_div == direction

    return {
        "timeframe": timeframe,
        "timeframe_label": TIMEFRAME_LABELS.get(timeframe, timeframe),
        "direction": direction,
        "close_price": close_price,
        "level_broken": level_broken,
        "candle_strength": strength,
        "candle_time": candle_time,
        "rsi_divergence_confirms": rsi_confirms,
        "rsi_divergence_value": rsi_div,
    }


def scan_multi_timeframe(fetch_func, symbol: str, timeframes: list = None) -> list[dict]:
    """
    يفحص عملة واحدة على كل الفريمات المطلوبة
    fetch_func: دالة تجلب البيانات (symbol, timeframe) -> DataFrame أو None

    يعيد قائمة بكل النتائج (إشارة واحدة كحد أقصى لكل فريم)
    """
    timeframes = timeframes or TIMEFRAMES
    results = []

    for tf in timeframes:
        df = fetch_func(symbol, tf)
        if df is None or len(df) < LEVEL_LOOKBACK + 5:
            continue

        result = check_candle_close(df, tf)
        if result:
            result["symbol"] = symbol
            results.append(result)

    return results
