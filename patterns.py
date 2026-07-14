"""
أنماط الشموع الكلاسيكية + Order Blocks (منطق Smart Money Concepts)

ملاحظة مهمة: Order Blocks مفهوم تحليلي اجتهادي (مدرسة SMC)، دقته متفاوتة
وليس قانوناً حتمياً. نستخدمه هنا كطبقة تأكيد إضافية (Confluence) تقوّي
الإشارة، وليس كشرط وحيد للدخول.
"""
import pandas as pd


# ============ أنماط الشموع ============

def body_size(row) -> float:
    return abs(row["close"] - row["open"])


def candle_range(row) -> float:
    return row["high"] - row["low"]


def is_bullish(row) -> bool:
    return row["close"] > row["open"]


def is_bearish(row) -> bool:
    return row["close"] < row["open"]


def detect_hammer(df: pd.DataFrame) -> bool:
    """
    المطرقة: شمعة بجسم صغير بالأعلى وذيل سفلي طويل (2x الجسم على الأقل)
    تظهر عادة بعد اتجاه هابط، إشارة ارتداد صعودي محتملة
    """
    last = df.iloc[-1]
    body = body_size(last)
    rng = candle_range(last)
    if rng == 0 or body == 0:
        return False

    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])

    return (
        lower_wick >= body * 2
        and upper_wick <= body * 0.5
        and body / rng < 0.35
    )


def detect_shooting_star(df: pd.DataFrame) -> bool:
    """
    النجمة الهاوية: عكس المطرقة، ذيل علوي طويل وجسم صغير بالأسفل
    تظهر بعد اتجاه صاعد، إشارة انعكاس هبوطي محتملة
    """
    last = df.iloc[-1]
    body = body_size(last)
    rng = candle_range(last)
    if rng == 0 or body == 0:
        return False

    upper_wick = last["high"] - max(last["open"], last["close"])
    lower_wick = min(last["open"], last["close"]) - last["low"]

    return (
        upper_wick >= body * 2
        and lower_wick <= body * 0.5
        and body / rng < 0.35
    )


def detect_bullish_engulfing(df: pd.DataFrame) -> bool:
    """ابتلاع صعودي: شمعة خضراء تبتلع جسم الشمعة الحمراء السابقة بالكامل"""
    if len(df) < 2:
        return False
    prev, last = df.iloc[-2], df.iloc[-1]

    return (
        is_bearish(prev)
        and is_bullish(last)
        and last["open"] <= prev["close"]
        and last["close"] >= prev["open"]
    )


def detect_bearish_engulfing(df: pd.DataFrame) -> bool:
    """ابتلاع هبوطي: شمعة حمراء تبتلع جسم الشمعة الخضراء السابقة بالكامل"""
    if len(df) < 2:
        return False
    prev, last = df.iloc[-2], df.iloc[-1]

    return (
        is_bullish(prev)
        and is_bearish(last)
        and last["open"] >= prev["close"]
        and last["close"] <= prev["open"]
    )


def detect_doji(df: pd.DataFrame, threshold: float = 0.1) -> bool:
    """
    الدوجي: الفتح والإغلاق شبه متساويين (تردد بالسوق)
    threshold: نسبة الجسم إلى المدى الكلي للشمعة
    """
    last = df.iloc[-1]
    rng = candle_range(last)
    if rng == 0:
        return False
    return body_size(last) / rng <= threshold


def detect_candle_patterns(df: pd.DataFrame) -> list[str]:
    """يفحص كل الأنماط على آخر شمعة، يعيد قائمة بأسماء الأنماط المكتشفة"""
    found = []
    if detect_hammer(df):
        found.append("مطرقة (ارتداد صعودي محتمل)")
    if detect_shooting_star(df):
        found.append("نجمة هاوية (انعكاس هبوطي محتمل)")
    if detect_bullish_engulfing(df):
        found.append("ابتلاع صعودي")
    if detect_bearish_engulfing(df):
        found.append("ابتلاع هبوطي")
    if detect_doji(df):
        found.append("دوجي (تردد بالسوق)")
    return found


# ============ Order Blocks ============

def find_bullish_order_block(df: pd.DataFrame, impulse_threshold: float = 0.03,
                               lookback: int = 15):
    """
    يبحث عن آخر Order Block صعودي:
    آخر شمعة هابطة قبل حركة صاعدة اندفاعية (>= impulse_threshold نسبة صعود)

    يعيد: (مستوى أعلى المنطقة, مستوى أسفل المنطقة) أو None إن لم يوجد
    """
    window = df.iloc[-(lookback + 5):-1].reset_index(drop=True)
    if len(window) < 4:
        return None

    for i in range(len(window) - 3, 0, -1):
        candle = window.iloc[i]
        if not is_bearish(candle):
            continue

        # نتحقق من حركة اندفاعية صعودية خلال الشمعتين/الثلاث التاليات
        future = window.iloc[i + 1: i + 4]
        if future.empty:
            continue

        move_up = (future["close"].max() - candle["close"]) / candle["close"]
        if move_up >= impulse_threshold:
            return candle["low"], candle["high"]

    return None


def find_bearish_order_block(df: pd.DataFrame, impulse_threshold: float = 0.03,
                               lookback: int = 15):
    """
    يبحث عن آخر Order Block هبوطي:
    آخر شمعة صاعدة قبل حركة هابطة اندفاعية

    يعيد: (مستوى أعلى المنطقة, مستوى أسفل المنطقة) أو None إن لم يوجد
    """
    window = df.iloc[-(lookback + 5):-1].reset_index(drop=True)
    if len(window) < 4:
        return None

    for i in range(len(window) - 3, 0, -1):
        candle = window.iloc[i]
        if not is_bullish(candle):
            continue

        future = window.iloc[i + 1: i + 4]
        if future.empty:
            continue

        move_down = (candle["close"] - future["close"].min()) / candle["close"]
        if move_down >= impulse_threshold:
            return candle["low"], candle["high"]

    return None


def price_near_zone(price: float, zone: tuple, tolerance: float = 0.005) -> bool:
    """يتحقق إذا كان السعر الحالي قريب من منطقة Order Block معينة"""
    if zone is None:
        return False
    low, high = zone
    margin = (high - low) * tolerance if high > low else price * tolerance
    return (low - margin) <= price <= (high + margin)
