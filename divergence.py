"""
كشف الدايفرجنس (Divergence) الإيجابي والسلبي على مؤشري RSI وMACD
مع اشتراط شمعة فوليوم ضخمة كتأكيد.

الدايفرجنس الإيجابي (صعودي): السعر يعمل قاع أدنى، لكن المؤشر يعمل قاع أعلى
   → ضعف بالزخم الهبوطي، احتمال انعكاس صعودي
الدايفرجنس السلبي (هبوطي): السعر يعمل قمة أعلى، لكن المؤشر يعمل قمة أدنى
   → ضعف بالزخم الصعودي، احتمال انعكاس هبوطي
"""
import pandas as pd


def calc_macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9):
    """يعيد (خط MACD، خط الإشارة، الهيستوجرام)"""
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    macd_line = ema_fast - ema_slow
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line
    return macd_line, signal_line, histogram


def find_local_extrema(series: pd.Series, order: int = 3):
    """
    يجد القمم والقيعان المحلية بسلسلة بيانات
    order: عدد النقاط على كل جانب يجب أن تكون أقل/أكبر منها
    يعيد: (قائمة مواقع القيعان، قائمة مواقع القمم)
    """
    lows, highs = [], []
    n = len(series)
    for i in range(order, n - order):
        window = series.iloc[i - order: i + order + 1]
        center = series.iloc[i]
        if center == window.min() and (window == center).sum() == 1:
            lows.append(i)
        if center == window.max() and (window == center).sum() == 1:
            highs.append(i)
    return lows, highs


def check_volume_spike(df: pd.DataFrame, multiplier: float = 2.0, period: int = 20) -> bool:
    """يتحقق إذا كانت آخر شمعة ذات حجم تداول ضخم مقارنة بالمعدل"""
    if len(df) < period + 1:
        return False
    avg_vol = df["volume"].iloc[-(period + 1):-1].mean()
    last_vol = df["volume"].iloc[-1]
    return avg_vol > 0 and last_vol >= avg_vol * multiplier


def detect_divergence(df: pd.DataFrame, indicator: pd.Series, lookback: int = 30,
                       order: int = 3):
    """
    يفحص وجود دايفرجنس بين السعر والمؤشر المُعطى (RSI أو خط MACD)
    ضمن آخر `lookback` شمعة، بمقارنة آخر قاعين محليين أو آخر قمتين محليتين

    يعيد: "bullish" / "bearish" / None
    """
    if len(df) < lookback + order * 2:
        return None

    window_price = df["close"].iloc[-lookback:].reset_index(drop=True)
    window_indicator = indicator.iloc[-lookback:].reset_index(drop=True)

    lows, highs = find_local_extrema(window_price, order=order)

    # دايفرجنس إيجابي (صعودي): آخر قاعين بالسعر
    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        price_lower_low = window_price.iloc[i2] < window_price.iloc[i1]
        indicator_higher_low = window_indicator.iloc[i2] > window_indicator.iloc[i1]
        if price_lower_low and indicator_higher_low:
            return "bullish"

    # دايفرجنس سلبي (هبوطي): آخر قمتين بالسعر
    if len(highs) >= 2:
        i1, i2 = highs[-2], highs[-1]
        price_higher_high = window_price.iloc[i2] > window_price.iloc[i1]
        indicator_lower_high = window_indicator.iloc[i2] < window_indicator.iloc[i1]
        if price_higher_high and indicator_lower_high:
            return "bearish"

    return None


def analyze_divergence(df: pd.DataFrame, rsi: pd.Series, volume_multiplier: float = 2.0):
    """
    يفحص الدايفرجنس على كل من RSI وMACD، ويتحقق من شمعة فوليوم ضخمة
    يعيد قاموساً بالنتائج: {"rsi": "bullish"/"bearish"/None, "macd": ..., "volume_spike": bool}
    """
    macd_line, _, _ = calc_macd(df["close"])
    volume_spike = check_volume_spike(df, multiplier=volume_multiplier)

    return {
        "rsi": detect_divergence(df, rsi),
        "macd": detect_divergence(df, macd_line),
        "volume_spike": volume_spike,
    }
