"""
حساب المؤشرات الفنية يدوياً باستخدام pandas فقط
(تجنباً للاعتماد على مكتبات خارجية قد لا تكون مستقرة على GitHub Actions)
"""
import pandas as pd


def calc_rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """حساب مؤشر RSI"""
    delta = close.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)

    avg_gain = gain.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, min_periods=period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))
    return rsi


def find_support_resistance(df: pd.DataFrame, lookback: int = 20):
    """
    إيجاد أقرب مستوى دعم ومقاومة خلال آخر `lookback` شمعة
    (باستثناء الشمعة الحالية غير المكتملة)
    """
    window = df.iloc[-(lookback + 1):-1]
    resistance = window["high"].max()
    support = window["low"].min()
    return support, resistance


def avg_volume(df: pd.DataFrame, period: int = 20) -> float:
    return df["volume"].iloc[-(period + 1):-1].mean()
