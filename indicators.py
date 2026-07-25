"""
حساب المؤشرات الفنية يدوياً باستخدام pandas و numpy فقط
(تجنباً للاعتماد على مكتبات خارجية قد لا تكون مستقرة على GitHub Actions)
"""
import pandas as pd
import numpy as np


# ==========================================
# 1. مؤشرات الزخم والاتجاه (RSI, EMA, Bollinger)
# ==========================================

def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    حساب مؤشر RSI باستخدام طريقة Wilder's Smoothing المعتمدة في TradingView
    """
    if close is None or len(close) < period + 1:
        return pd.Series(dtype=float)

    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.iloc[1:period + 1].mean()
    avg_loss = loss.iloc[1:period + 1].mean()

    gains = [np.nan] * period + [avg_gain]
    losses = [np.nan] * period + [avg_loss]

    for i in range(period + 1, len(close)):
        avg_gain = (avg_gain * (period - 1) + gain.iloc[i]) / period
        avg_loss = (avg_loss * (period - 1) + loss.iloc[i]) / period
        gains.append(avg_gain)
        losses.append(avg_loss)

    avg_gain_series = pd.Series(gains, index=close.index)
    avg_loss_series = pd.Series(losses, index=close.index)

    rs = avg_gain_series / avg_loss_series.replace(0, 1e-10)
    rsi = 100.0 - (100.0 / (1.0 + rs))
    return rsi


def calc_ema(close: pd.Series, period: int = 20) -> pd.Series:
    """حساب المتوسط المتحرك الأسي (EMA)"""
    if close is None or len(close) < period:
        return pd.Series(dtype=float)
    return close.ewm(span=period, adjust=False).mean()


def calc_bollinger_bands(close: pd.Series, period: int = 20, std_dev: float = 2.0):
    """
    حساب نطاقات بولينجر (العلمي، المتوسط، والسفلي)
    يعيد: (النطاق السفلي, المتوسط المتحرك, النطاق العلوي)
    """
    if close is None or len(close) < period:
        empty_s = pd.Series(dtype=float)
        return empty_s, empty_s, empty_s

    sma = close.rolling(window=period).mean()
    std = close.rolling(window=period).std()
    upper = sma + (std * std_dev)
    lower = sma - (std * std_dev)
    return lower, sma, upper


# ==========================================
# 2. تحليلات الأحجام والسيولة (Volume Analysis)
# ==========================================

def avg_volume(df: pd.DataFrame, period: int = 20) -> float:
    """حساب متوسط حجم التداول للشموع المكتملة"""
    if df is None or len(df) < 2 or "volume" not in df.columns:
        return 0.0

    actual_period = min(len(df) - 1, period)
    window = df["volume"].iloc[-(actual_period + 1):-1]
    val = window.mean()
    return float(val) if not np.isnan(val) else 0.0


def volume_spike_ratio(df: pd.DataFrame, period: int = 20) -> float:
    """
    يحسب نسبة حجم الشمعة الحالية مقارنة بمتوسط الشموع السابقة.
    مثال: النتيجة 2.5 تعني أن حجم الشمعة الحالية أعلى بـ 150% من المتوسط.
    """
    if df is None or len(df) < period + 1 or "volume" not in df.columns:
        return 1.0

    current_vol = df["volume"].iloc[-1]
    avg_vol = avg_volume(df, period=period)

    if avg_vol == 0:
        return 1.0

    return round(float(current_vol / avg_vol), 2)


# ==========================================
# 3. مستويات الدعم/المقاومة وفحص الاختراقات
# ==========================================

def find_support_resistance(df: pd.DataFrame, lookback: int = 20):
    """
    إيجاد أقرب مستوى دعم ومقاومة خلال آخر `lookback` شمعة
    """
    if df is None or len(df) < lookback + 1:
        return 0.0, 0.0

    window = df.iloc[-(lookback + 1):-1]
    resistance = window["high"].max()
    support = window["low"].min()

    return float(support), float(resistance)


def check_breakout(df: pd.DataFrame, lookback: int = 20) -> dict:
    """
    فحص هل أغلقت الشمعة الحالية فوق المقاومة (اختراق صاعد) 
    أو تحت الدعم (كسر هابط) مع نسبة الاختراق
    """
    default_res = {
        "is_bullish_breakout": False,
        "is_bearish_breakout": False,
        "support": 0.0,
        "resistance": 0.0,
        "last_price": 0.0
    }

    if df is None or len(df) < lookback + 1:
        return default_res

    support, resistance = find_support_resistance(df, lookback=lookback)
    last_close = float(df["close"].iloc[-1])

    return {
        "is_bullish_breakout": last_close > resistance and resistance > 0,
        "is_bearish_breakout": last_close < support and support > 0,
        "support": support,
        "resistance": resistance,
        "last_price": last_close
    }
