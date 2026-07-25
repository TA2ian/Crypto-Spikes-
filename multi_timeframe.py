"""
فحص إغلاق الشمعة على عدة فريمات (1h, 4h, 1d, 1w) مع التجميع المحلي السريع (Resampling)
والتطوير بالتوازي وأوزان النقاط الديناميكية.

إشارة إيجابية: شمعة خضراء + إغلاق فوق مستوى مقاومة/قمة سابقة بارزة
إشارة سلبية: شمعة حمراء + إغلاق تحت مستوى دعم/قاع سابق بارز
"""
import pandas as pd
import numpy as np
from concurrent.futures import ThreadPoolExecutor

# جلب الدوال من الملفات المعتمدة
try:
    from technical_tools import calc_rsi, find_support_resistance
except ImportError:
    from indicators import calc_rsi, find_support_resistance

try:
    from divergence import detect_divergence
except ImportError:
    def detect_divergence(df, rsi, lookback=30, order=3):
        return None


TIMEFRAMES = ["1hour", "4hour", "1day", "1week"]

TIMEFRAME_LABELS = {
    "1hour": "1h",
    "4hour": "4h",
    "1day": "1d",
    "1week": "1w",
}

# خطة (3): أوزان الفريمات الديناميكية بحسب الأهمية الهيكلية
TIMEFRAME_WEIGHTS = {
    "1hour": 1.0,
    "4hour": 1.5,
    "1day": 2.5,
    "1week": 3.5,
}

LEVEL_LOOKBACK = 20   # فترة حساب المستوى (دعم/مقاومة) لكل فريم
MIN_BODY_RATIO = 0.3  # الحد الأدنى لجسم الشمعة كنسبة من مداها لاعتبارها "قوية"


def candle_strength(row) -> float:
    """نسبة جسم الشمعة إلى مداها الكلي (0 = دوجي، 1 = بدون ذيول)"""
    rng = row["high"] - row["low"]
    if rng == 0:
        return 0.0
    return abs(row["close"] - row["open"]) / rng


# خطة (1): تحويل الشموع محلياً لتوفير طلبات الـ API
def resample_klines(df_1h: pd.DataFrame, target_timeframe: str) -> pd.DataFrame:
    """
    تحوّل DataFrame لشموع 1h إلى فريمات أكبر (4h, 1d, 1w) دون الحاجة لطلب API جديد.
    """
    if target_timeframe == "1hour" or df_1h is None or df_1h.empty:
        return df_1h

    rule_map = {
        "4hour": "4h",
        "1day": "1D",
        "1week": "1W",
    }
    
    rule = rule_map.get(target_timeframe)
    if not rule:
        return df_1h

    df_copy = df_1h.copy()

    # تحويل الطابع الزمني إلى DatetimeIndex إن لم يكن كذلك
    if "time" in df_copy.columns:
        if pd.api.types.is_numeric_dtype(df_copy["time"]):
            df_copy["datetime"] = pd.to_datetime(df_copy["time"], unit="s", errors="coerce")
        else:
            df_copy["datetime"] = pd.to_datetime(df_copy["time"], errors="coerce")
        df_copy.set_index("datetime", inplace=True)

    try:
        resampled = df_copy.resample(rule).agg({
            "open": "first",
            "high": "max",
            "low": "min",
            "close": "last",
            "volume": "sum",
        }).dropna().reset_index()

        # إعادة عمود time الأصلي بصيغة ثواني
        resampled["time"] = resampled["datetime"].astype("int64") // 10**9
        return resampled
    except Exception:
        return df_1h


def check_candle_close(df: pd.DataFrame, timeframe: str):
    """
    يفحص إغلاق آخر شمعة **مقفولة بالكامل** مقابل مستوى الدعم/المقاومة للشموع السابقة لها.
    """
    if df is None or len(df) < LEVEL_LOOKBACK + 5:
        return None

    last_closed = df.iloc[-2]
    historical_df = df.iloc[:-2]

    if len(historical_df) < LEVEL_LOOKBACK:
        return None

    window = historical_df.iloc[-LEVEL_LOOKBACK:]
    support = float(window["low"].min())
    resistance = float(window["high"].max())

    strength = candle_strength(last_closed)
    
    if strength < MIN_BODY_RATIO:
        return None

    is_bullish = last_closed["close"] > last_closed["open"]
    is_bearish = last_closed["close"] < last_closed["open"]

    close_price = float(last_closed["close"])
    candle_time = int(last_closed["time"]) if "time" in last_closed and not np.isnan(last_closed["time"]) else None

    direction = None
    level_broken = None

    if is_bullish and close_price > resistance and resistance > 0:
        direction = "bullish"
        level_broken = resistance
    elif is_bearish and close_price < support and support > 0:
        direction = "bearish"
        level_broken = support

    if direction is None:
        return None

    # تأكيد دايفرجنس RSI
    closed_series = df.iloc[:-1]
    rsi = calc_rsi(closed_series["close"], 14)
    
    rsi_div = None
    try:
        rsi_div = detect_divergence(closed_series, rsi)
    except Exception:
        rsi_div = None

    rsi_confirms = (rsi_div == direction)

    return {
        "timeframe": timeframe,
        "timeframe_label": TIMEFRAME_LABELS.get(timeframe, timeframe),
        "tf_weight": TIMEFRAME_WEIGHTS.get(timeframe, 1.0),  # الوزن المضاف
        "direction": direction,
        "close_price": close_price,
        "level_broken": level_broken,
        "candle_strength": round(strength, 2),
        "candle_time": candle_time,
        "rsi_divergence_confirms": rsi_confirms,
        "rsi_divergence_value": rsi_div,
    }


def scan_multi_timeframe(fetch_func, symbol: str, timeframes: list = None, use_resampling: bool = True) -> list[dict]:
    """
    يفحص عملة واحدة عبر الفريمات بسرعة فائقة بالتوازي وتوليد الفريمات محلياً.
    """
    timeframes = timeframes or TIMEFRAMES
    results = []

    # إذا تم تفعيل التجميع المحلي، نكتفي بجلب فريم 1h مرة واحدة فقط!
    if use_resampling:
        df_1h = fetch_func(symbol, "1hour")
        if df_1h is None or len(df_1h) < LEVEL_LOOKBACK + 5:
            return results

        def process_tf_resampled(tf):
            df_tf = resample_klines(df_1h, tf) if tf != "1hour" else df_1h
            res = check_candle_close(df_tf, tf)
            if res:
                res["symbol"] = symbol
            return res

        # خطة (2): معالجة الفريمات المجمعة بالتوازي
        with ThreadPoolExecutor(max_workers=len(timeframes)) as executor:
            futures = executor.map(process_tf_resampled, timeframes)
            for res in futures:
                if res:
                    results.append(res)

    else:
        # الطريقة التقليدية بالجلب من API
        def process_tf_direct(tf):
            try:
                df = fetch_func(symbol, tf)
                if df is not None and len(df) >= LEVEL_LOOKBACK + 5:
                    res = check_candle_close(df, tf)
                    if res:
                        res["symbol"] = symbol
                        return res
            except Exception:
                pass
            return None

        with ThreadPoolExecutor(max_workers=len(timeframes)) as executor:
            futures = executor.map(process_tf_direct, timeframes)
            for res in futures:
                if res:
                    results.append(res)

    return results
