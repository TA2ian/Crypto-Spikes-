"""
CVD تقريبي (Cumulative Volume Delta) — تقدير ضغط الشراء مقابل البيع

ملاحظة منهجية مهمة: هذا تقريب إحصائي معروف (يعتمد على مبدأ Close Location
Value)، وليس قياساً حقيقياً لصفقات الشراء/البيع الفعلية (تلك البيانات
تحتاج Tick Data أو Order Flow حقيقي، غير متوفرة مجاناً من KuCoin العام).

المبدأ: كل ما أغلق السعر قريباً من أعلى الشمعة، افترضنا أن أغلب حجمها
كان ضغط شراء. كل ما أغلق قريباً من أدنى الشمعة، افترضنا العكس.
"""
import pandas as pd


def close_location_value(row) -> float:
    """
    يحسب موقع الإغلاق ضمن مدى الشمعة (0 = أغلق عند الأدنى، 1 = أغلق عند الأعلى)
    القيمة 0.5 تعني إغلاق في منتصف المدى تماماً (توازن شراء/بيع)
    """
    rng = row["high"] - row["low"]
    if rng == 0:
        return 0.5
    return (row["close"] - row["low"]) / rng


def estimate_buy_sell_volume(df: pd.DataFrame) -> pd.DataFrame:
    """
    يضيف أعمدة تقديرية لحجم الشراء والبيع لكل شمعة، بناءً على موقع الإغلاق
    يعيد نسخة من df مع أعمدة إضافية: clv, buy_volume, sell_volume, delta
    """
    result = df.copy()
    clv = result.apply(close_location_value, axis=1)

    result["clv"] = clv
    result["buy_volume"] = result["volume"] * clv
    result["sell_volume"] = result["volume"] * (1 - clv)
    result["delta"] = result["buy_volume"] - result["sell_volume"]

    return result


def calc_cvd(df: pd.DataFrame) -> pd.Series:
    """يحسب CVD كمجموع تراكمي لـ Delta عبر الزمن"""
    enriched = estimate_buy_sell_volume(df)
    return enriched["delta"].cumsum()


def cvd_trend(df: pd.DataFrame, lookback: int = 10) -> str:
    """
    يحدد اتجاه CVD الأخير (هل ضغط الشراء التراكمي يتزايد أم يتناقص)
    يعيد: "شراء متزايد" / "بيع متزايد" / "متوازن"
    """
    cvd = calc_cvd(df)
    if len(cvd) < lookback + 1:
        return "غير محدد"

    recent_change = cvd.iloc[-1] - cvd.iloc[-lookback]
    avg_volume = df["volume"].iloc[-lookback:].mean()

    if avg_volume == 0:
        return "غير محدد"

    # نسبة التغير مقارنة بمتوسط الحجم، لتطبيع القيمة بين عملات مختلفة السيولة
    normalized_change = recent_change / (avg_volume * lookback)

    if normalized_change > 0.05:
        return "شراء متزايد"
    elif normalized_change < -0.05:
        return "بيع متزايد"
    return "متوازن"


def detect_cvd_divergence(df: pd.DataFrame, lookback: int = 30, order: int = 3):
    """
    يفحص دايفرجنس بين السعر وCVD (نفس منطق دايفرجنس RSI/MACD لكن على CVD)
    مفيد لرصد حالات: السعر يصعد لكن ضغط الشراء الحقيقي يضعف (تحذير انعكاس)

    يعيد: "bullish" / "bearish" / None
    """
    from divergence import detect_divergence

    cvd = calc_cvd(df)
    return detect_divergence(df, cvd, lookback=lookback, order=order)


def analyze_cvd(df: pd.DataFrame) -> dict:
    """يجمع كل تحليلات CVD بمكان واحد لدمجها بسهولة بباقي طبقات التحليل"""
    return {
        "trend": cvd_trend(df),
        "divergence": detect_cvd_divergence(df),
        "last_clv": close_location_value(df.iloc[-1]),
    }
