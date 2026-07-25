"""
أدوات فيبوناتشي: التصحيحي (Retracement)، الامتدادي (Extension)، والزمني (Time Zones)

ملاحظة تحليلية مهمة: فيبوناتشي الزمني هو الأقل موثوقية إحصائياً بين الثلاثة
حتى بأدبيات التحليل الفني الكلاسيكي. نستخدمه هنا كمعلومة سياقية إضافية فقط،
وليس كإشارة دخول أو تأكيد.
"""
import pandas as pd
import numpy as np

FIB_RETRACEMENT_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_EXTENSION_LEVELS = [1.272, 1.618, 2.0, 2.618]
FIB_TIME_RATIOS = [1, 2, 3, 5, 8, 13, 21]


def find_recent_swing(df: pd.DataFrame, lookback: int = 30):
    """
    يجد آخر قمة وقاع بارزين خلال فترة النظر للخلف مع الاحتفاظ بالقيم والمواقع الصحيحة
    """
    if df is None or len(df) < lookback:
        return 0, 0.0, 0, 0.0

    window = df.iloc[-lookback:]
    low_idx = window["low"].idxmin()
    high_idx = window["high"].idxmax()
    
    # تحويل Index إلى مواقع نسبية داخل النافذة (من 0 إلى lookback-1)
    low_pos = window.index.get_loc(low_idx)
    high_pos = window.index.get_loc(high_idx)

    return low_pos, window["low"].loc[low_idx], high_pos, window["high"].loc[high_idx]


def calc_fib_retracement(swing_low: float, swing_high: float) -> dict:
    """
    يحسب مستويات التصحيح بين قاع وقمة
    """
    diff = swing_high - swing_low
    if diff <= 0:
        return {}

    levels = {}
    for ratio in FIB_RETRACEMENT_LEVELS:
        levels[ratio] = round(swing_high - (diff * ratio), 6)
    return levels


def calc_fib_extension(swing_low: float, swing_high: float, direction: str = "up") -> dict:
    """
    يحسب مستويات الامتداد بأسلوب التحليل الفني القياسي
    """
    diff = swing_high - swing_low
    if diff <= 0:
        return {}

    levels = {}
    for ratio in FIB_EXTENSION_LEVELS:
        if direction == "up":
            levels[ratio] = round(swing_high + (diff * (ratio - 1)), 6)
        else:
            levels[ratio] = round(swing_low - (diff * (ratio - 1)), 6)
    return levels


def calc_fib_time_zones(swing_start_idx: int) -> list:
    """
    يحسب مناطق فيبوناتشي الزمنية المحتملة (بعدد الشموع من نقطة البداية)
    """
    return [swing_start_idx + ratio for ratio in FIB_TIME_RATIOS]


def nearest_fib_level(price: float, levels: dict, tolerance: float = 0.01):
    """
    يتحقق أي مستوى فيبوناتشي أقرب للسعر الحالي ضمن هامش تسامح مئوي
    """
    if not levels or price <= 0:
        return None

    for ratio, level_price in levels.items():
        if level_price == 0:
            continue
        if abs(price - level_price) / level_price <= tolerance:
            return ratio, level_price
    return None


def analyze_fibonacci(df: pd.DataFrame, lookback: int = 30, tolerance: float = 0.01) -> dict:
    """
    يحسب كل مستويات فيبوناتشي ويحدد القريب منها للسعر الحالي
    """
    default_res = {
        "swing_low": 0.0,
        "swing_high": 0.0,
        "direction": "flat",
        "retracement_levels": {},
        "extension_levels": {},
        "time_zones": [],
        "near_retracement": None,
        "near_extension": None,
    }

    if df is None or len(df) < lookback or "close" not in df.columns:
        return default_res

    low_pos, swing_low, high_pos, swing_high = find_recent_swing(df, lookback)
    
    if swing_low == swing_high or swing_low == 0:
        return default_res

    last_price = df["close"].iloc[-1]

    # إذا كان القاع حدث قبل القمة -> الاتجاه صاعد (الصعود هو الحركة الأخيرة)
    direction = "up" if low_pos < high_pos else "down"

    retracement = calc_fib_retracement(swing_low, swing_high)
    extension = calc_fib_extension(swing_low, swing_high, direction=direction)
    time_zones = calc_fib_time_zones(min(low_pos, high_pos))

    near_retracement = nearest_fib_level(last_price, retracement, tolerance=tolerance)
    near_extension = nearest_fib_level(last_price, extension, tolerance=tolerance)

    return {
        "swing_low": swing_low,
        "swing_high": swing_high,
        "direction": direction,
        "retracement_levels": retracement,
        "extension_levels": extension,
        "time_zones": time_zones,
        "near_retracement": near_retracement,
        "near_extension": near_extension,
    }
