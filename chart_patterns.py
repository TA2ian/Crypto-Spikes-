"""
كشف النماذج السعرية الكلاسيكية: قاع/قمة مزدوجة، رأس وكتفين، مثلثات،
علم (Flag)، قناة سعرية، واتجاه عام (Trend).

ملاحظة منهجية: هذه أنماط بصرية بطبيعتها، وخوارزميات كشفها الآلي تحتمل
نسبة إشارات كاذبة أعلى من المؤشرات الرياضية البحتة (RSI، فيبوناتشي).
تُعامل هنا كطبقة معلوماتية تحتاج تأكيد العين البشرية دائماً.
"""
import pandas as pd
from divergence import find_local_extrema


def detect_trend(df: pd.DataFrame, lookback: int = 20) -> str:
    """
    يحدد الاتجاه العام بمقارنة متوسطين متحركين بسيطين
    يعيد: "صاعد" / "هابط" / "عرضي"
    """
    close = df["close"]
    if len(close) < lookback:
        return "غير محدد"

    short_ma = close.rolling(window=lookback // 2).mean().iloc[-1]
    long_ma = close.rolling(window=lookback).mean().iloc[-1]

    diff_pct = (short_ma - long_ma) / long_ma if long_ma else 0

    if diff_pct > 0.005:
        return "صاعد"
    elif diff_pct < -0.005:
        return "هابط"
    return "عرضي"


def detect_double_top_bottom(df: pd.DataFrame, lookback: int = 40, order: int = 3,
                               tolerance: float = 0.015):
    """
    يكشف نموذج القمة المزدوجة أو القاع المزدوج
    tolerance: نسبة التقارب المسموحة بين القمتين/القاعين لاعتبارهما "متساويين"

    يعيد: "قمة مزدوجة" / "قاع مزدوج" / None
    """
    if len(df) < lookback:
        return None

    window = df["close"].iloc[-lookback:].reset_index(drop=True)
    lows, highs = find_local_extrema(window, order=order)

    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        p1, p2 = window.iloc[h1], window.iloc[h2]
        if abs(p1 - p2) / p1 <= tolerance:
            return "قمة مزدوجة"

    if len(lows) >= 2:
        l1, l2 = lows[-2], lows[-1]
        p1, p2 = window.iloc[l1], window.iloc[l2]
        if abs(p1 - p2) / p1 <= tolerance:
            return "قاع مزدوج"

    return None


def detect_head_and_shoulders(df: pd.DataFrame, lookback: int = 50, order: int = 3,
                                shoulder_tolerance: float = 0.03):
    """
    يكشف نموذج الرأس والكتفين (هبوطي) أو المقلوب (صاعد)
    يحتاج 3 قمم/قيعان متتالية: كتف-رأس-كتف بنمط محدد

    يعيد: "رأس وكتفين هابط" / "رأس وكتفين صاعد (مقلوب)" / None
    """
    if len(df) < lookback:
        return None

    window = df["close"].iloc[-lookback:].reset_index(drop=True)
    lows, highs = find_local_extrema(window, order=order)

    # رأس وكتفين عادي (هبوطي): 3 قمم، الوسطى أعلى من الطرفين المتقاربين
    if len(highs) >= 3:
        h1, h2, h3 = highs[-3], highs[-2], highs[-1]
        p1, p2, p3 = window.iloc[h1], window.iloc[h2], window.iloc[h3]
        shoulders_equal = abs(p1 - p3) / p1 <= shoulder_tolerance
        head_higher = p2 > p1 and p2 > p3
        if shoulders_equal and head_higher:
            return "رأس وكتفين هابط"

    # رأس وكتفين مقلوب (صاعد): 3 قيعان، الوسطى أدنى من الطرفين المتقاربين
    if len(lows) >= 3:
        l1, l2, l3 = lows[-3], lows[-2], lows[-1]
        p1, p2, p3 = window.iloc[l1], window.iloc[l2], window.iloc[l3]
        shoulders_equal = abs(p1 - p3) / p1 <= shoulder_tolerance
        head_lower = p2 < p1 and p2 < p3
        if shoulders_equal and head_lower:
            return "رأس وكتفين صاعد (مقلوب)"

    return None


def detect_triangle(df: pd.DataFrame, lookback: int = 30, order: int = 3):
    """
    يكشف نمط المثلث بمقارنة ميل خط القمم مع ميل خط القيعان
    مثلث صاعد: مقاومة أفقية + دعم صاعد
    مثلث هابط: دعم أفقي + مقاومة هابطة
    مثلث متماثل: كلا الخطين يتقاربان

    يعيد: "مثلث صاعد" / "مثلث هابط" / "مثلث متماثل" / None
    """
    if len(df) < lookback:
        return None

    window = df.iloc[-lookback:].reset_index(drop=True)
    lows_idx, highs_idx = find_local_extrema(window["close"], order=order)

    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return None

    # ميل خط القمم (نأخذ آخر قمتين)
    h1, h2 = highs_idx[-2], highs_idx[-1]
    high_slope = (window["high"].iloc[h2] - window["high"].iloc[h1]) / max(h2 - h1, 1)

    # ميل خط القيعان (نأخذ آخر قاعين)
    l1, l2 = lows_idx[-2], lows_idx[-1]
    low_slope = (window["low"].iloc[l2] - window["low"].iloc[l1]) / max(l2 - l1, 1)

    flat_threshold = window["close"].mean() * 0.0015  # هامش اعتبار الخط "أفقي"

    high_flat = abs(high_slope) < flat_threshold
    low_flat = abs(low_slope) < flat_threshold

    if high_flat and low_slope > flat_threshold:
        return "مثلث صاعد"
    if low_flat and high_slope < -flat_threshold:
        return "مثلث هابط"
    if high_slope < -flat_threshold and low_slope > flat_threshold:
        return "مثلث متماثل"

    return None


def detect_channel(df: pd.DataFrame, lookback: int = 30, order: int = 3):
    """
    يكشف قناة سعرية (صاعدة أو هابطة) بمقارنة ميل خطي القمم والقيعان
    عندما يكونان متوازيين تقريباً بنفس الاتجاه

    يعيد: "قناة صاعدة" / "قناة هابطة" / None
    """
    if len(df) < lookback:
        return None

    window = df.iloc[-lookback:].reset_index(drop=True)
    lows_idx, highs_idx = find_local_extrema(window["close"], order=order)

    if len(highs_idx) < 2 or len(lows_idx) < 2:
        return None

    h1, h2 = highs_idx[-2], highs_idx[-1]
    high_slope = (window["high"].iloc[h2] - window["high"].iloc[h1]) / max(h2 - h1, 1)

    l1, l2 = lows_idx[-2], lows_idx[-1]
    low_slope = (window["low"].iloc[l2] - window["low"].iloc[l1]) / max(l2 - l1, 1)

    avg_price = window["close"].mean()
    min_slope_threshold = avg_price * 0.0008

    both_rising = high_slope > min_slope_threshold and low_slope > min_slope_threshold
    both_falling = high_slope < -min_slope_threshold and low_slope < -min_slope_threshold

    # نتحقق أن الميلين متقاربين نسبياً (خطوط شبه متوازية)
    slopes_similar = abs(high_slope - low_slope) < avg_price * 0.002

    if both_rising and slopes_similar:
        return "قناة صاعدة"
    if both_falling and slopes_similar:
        return "قناة هابطة"

    return None


def detect_flag(df: pd.DataFrame, pole_lookback: int = 15, flag_lookback: int = 8,
                 pole_threshold: float = 0.05):
    """
    يكشف نموذج العلم: حركة اندفاعية قوية (Pole) يتبعها تصحيح هادئ ومحصور (Flag)
    علم صاعد: عمود صاعد قوي + تصحيح هابط/عرضي هادئ
    علم هابط: عمود هابط قوي + تصحيح صاعد/عرضي هادئ

    يعيد: "علم صاعد" / "علم هابط" / None
    """
    total_needed = pole_lookback + flag_lookback
    if len(df) < total_needed:
        return None

    pole_window = df["close"].iloc[-total_needed:-flag_lookback]
    flag_window = df["close"].iloc[-flag_lookback:]

    pole_move = (pole_window.iloc[-1] - pole_window.iloc[0]) / pole_window.iloc[0]
    flag_volatility = (flag_window.max() - flag_window.min()) / flag_window.mean()

    # العلم يجب أن يكون هادئاً نسبياً مقارنة بقوة العمود
    is_tight_flag = flag_volatility < abs(pole_move) * 0.5

    if pole_move >= pole_threshold and is_tight_flag:
        return "علم صاعد"
    if pole_move <= -pole_threshold and is_tight_flag:
        return "علم هابط"

    return None


def detect_all_patterns(df: pd.DataFrame) -> dict:
    """يشغّل كل كاشفات النماذج السعرية ويعيد قاموساً شاملاً بالنتائج"""
    return {
        "trend": detect_trend(df),
        "double_pattern": detect_double_top_bottom(df),
        "head_shoulders": detect_head_and_shoulders(df),
        "triangle": detect_triangle(df),
        "channel": detect_channel(df),
        "flag": detect_flag(df),
    }
