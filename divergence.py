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
    """يجد القمم والقيعان المحلية بسلسلة بيانات"""
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


def detect_divergence_with_volume(df: pd.DataFrame, indicator: pd.Series, lookback: int = 30, 
                                   order: int = 3, vol_multiplier: float = 2.0):
    """
    يفحص الدايفرجنس مع التحقق من وجود فوليوم ضخم عند شمعة الانعكاس الأحدث (i2) أو الشمعة الحالية.
    """
    if len(df) < lookback + order * 2:
        return {"signal": None, "volume_confirmed": False}

    # اقتطاع النافذة المحددة
    window_price = df["close"].iloc[-lookback:].reset_index(drop=True)
    window_volume = df["volume"].iloc[-lookback:].reset_index(drop=True)
    window_indicator = indicator.iloc[-lookback:].reset_index(drop=True)

    # حساب المتوسط المتحرك للحجم
    vol_sma = window_volume.rolling(window=20, min_periods=1).mean()

    lows, highs = find_local_extrema(window_price, order=order)

    # 1. دايفرجنس إيجابي (صعودي)
    if len(lows) >= 2:
        i1, i2 = lows[-2], lows[-1]
        price_lower_low = window_price.iloc[i2] < window_price.iloc[i1]
        indicator_higher_low = window_indicator.iloc[i2] > window_indicator.iloc[i1]

        if price_lower_low and indicator_higher_low:
            # التحقق من وجود فوليوم ضخم عند القاع الأحدث أو الشموع المجاورة له مباشرة
            vol_at_pivot = window_volume.iloc[i2]
            avg_vol_at_pivot = vol_sma.iloc[i2]
            has_volume_spike = vol_at_pivot >= (avg_vol_at_pivot * vol_multiplier)

            return {"signal": "bullish", "volume_confirmed": has_volume_spike}

    # 2. دايفرجنس سلبي (هبوطي)
    if len(highs) >= 2:
        i1, i2 = highs[-2], highs[-1]
        price_higher_high = window_price.iloc[i2] > window_price.iloc[i1]
        indicator_lower_high = window_indicator.iloc[i2] < window_indicator.iloc[i1]

        if price_higher_high and indicator_lower_high:
            vol_at_pivot = window_volume.iloc[i2]
            avg_vol_at_pivot = vol_sma.iloc[i2]
            has_volume_spike = vol_at_pivot >= (avg_vol_at_pivot * vol_multiplier)

            return {"signal": "bearish", "volume_confirmed": has_volume_spike}

    return {"signal": None, "volume_confirmed": False}


def analyze_divergence(df: pd.DataFrame, rsi: pd.Series, volume_multiplier: float = 2.0):
    """التحليل الشامل للـ RSI و MACD مع كشف سبايك الفوليوم"""
    macd_line, _, _ = calc_macd(df["close"])

    rsi_res = detect_divergence_with_volume(df, rsi, vol_multiplier=volume_multiplier)
    macd_res = detect_divergence_with_volume(df, macd_line, vol_multiplier=volume_multiplier)

    return {
        "rsi_signal": rsi_res["signal"],
        "rsi_volume_confirmed": rsi_res["volume_confirmed"],
        "macd_signal": macd_res["signal"],
        "macd_volume_confirmed": macd_res["volume_confirmed"],
    }
