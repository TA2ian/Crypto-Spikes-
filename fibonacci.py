"""
أدوات فيبوناتشي: التصحيحي (Retracement)، الامتدادي (Extension)، والزمني (Time Zones)

ملاحظة تحليلية مهمة: فيبوناتشي الزمني هو الأقل موثوقية إحصائياً بين الثلاثة
حتى بأدبيات التحليل الفني الكلاسيكي (يعتمد على افتراض تكرار الأنماط الزمنية
وهو أمر مختلف عليه بين المحللين). نستخدمه هنا كمعلومة سياقية إضافية فقط،
وليس كإشارة دخول أو تأكيد.
"""
import pandas as pd

FIB_RETRACEMENT_LEVELS = [0.236, 0.382, 0.5, 0.618, 0.786]
FIB_EXTENSION_LEVELS = [1.272, 1.618, 2.0, 2.618]
FIB_TIME_RATIOS = [1, 2, 3, 5, 8, 13, 21]  # متتالية فيبوناتشي كفترات زمنية (عدد شموع)


def find_recent_swing(df: pd.DataFrame, lookback: int = 30):
    """
    يجد آخر قمة وقاع بارزين خلال فترة النظر للخلف
    يعيد: (موقع القاع, سعر القاع, موقع القمة, سعر القمة)
    """
    window = df.iloc[-lookback:].reset_index(drop=True)
    low_idx = window["low"].idxmin()
    high_idx = window["high"].idxmax()
    return low_idx, window["low"].iloc[low_idx], high_idx, window["high"].iloc[high_idx]


def calc_fib_retracement(swing_low: float, swing_high: float) -> dict:
    """
    يحسب مستويات التصحيح بين قاع وقمة
    تُستخدم لتحديد مناطق التصحيح المحتملة أثناء اتجاه قائم
    """
    diff = swing_high - swing_low
    levels = {}
    for ratio in FIB_RETRACEMENT_LEVELS:
        levels[ratio] = swing_high - diff * ratio
    return levels


def calc_fib_extension(swing_low: float, swing_high: float, direction: str = "up") -> dict:
    """
    يحسب مستويات الامتداد (الأهداف المحتملة بعد اختراق القمة/القاع السابق)
    direction: "up" للاتجاه الصعودي، "down" للهبوطي
    """
    diff = swing_high - swing_low
    levels = {}
    for ratio in FIB_EXTENSION_LEVELS:
        if direction == "up":
            levels[ratio] = swing_high + diff * (ratio - 1)
        else:
            levels[ratio] = swing_low - diff * (ratio - 1)
    return levels


def calc_fib_time_zones(swing_start_idx: int, candle_interval_hours: float = 1.0):
    """
    يحسب مناطق فيبوناتشي الزمنية المحتملة (بعدد الشموع من نقطة البداية)
    هذه معلومة سياقية فقط - راجع الملاحظة أعلى الملف

    يعيد: قائمة بعدد الشموع المتوقعة لنقاط تحول زمنية محتملة
    """
    return [swing_start_idx + ratio for ratio in FIB_TIME_RATIOS]


def nearest_fib_level(price: float, levels: dict, tolerance: float = 0.01):
    """
    يتحقق أي مستوى فيبوناتشي أقرب للسعر الحالي ضمن هامش تسامح معين
    يعيد: (النسبة, السعر عند هذا المستوى) أو None
    """
    for ratio, level_price in levels.items():
        if level_price == 0:
            continue
        if abs(price - level_price) / level_price <= tolerance:
            return ratio, level_price
    return None


def analyze_fibonacci(df: pd.DataFrame, lookback: int = 30):
    """
    يحسب كل مستويات فيبوناتشي بناءً على آخر تأرجح (Swing) بالسعر
    يعيد قاموساً شاملاً بالمستويات وأقرب مستوى للسعر الحالي
    """
    low_idx, swing_low, high_idx, swing_high = find_recent_swing(df, lookback)
    last_price = df["close"].iloc[-1]

    # تحديد اتجاه الحركة الأخيرة (هل القاع قبل القمة أم بعدها؟)
    direction = "up" if low_idx < high_idx else "down"

    retracement = calc_fib_retracement(swing_low, swing_high)
    extension = calc_fib_extension(swing_low, swing_high, direction=direction)
    time_zones = calc_fib_time_zones(min(low_idx, high_idx))

    near_retracement = nearest_fib_level(last_price, retracement, tolerance=0.008)
    near_extension = nearest_fib_level(last_price, extension, tolerance=0.008)

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
