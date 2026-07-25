"""
CVD تقريبي (Cumulative Volume Delta) — تقدير ضغط الشراء مقابل البيع

ملاحظة منهجية مهمة: هذا تقريب إحصائي معروف (يعتمد على مبدأ Close Location
Value)، وليس قياساً حقيقياً لصفقات الشراء/البيع الفعلية (تلك البيانات
تحتاج Tick Data أو Order Flow حقيقي، غير متوفرة مجاناً من KuCoin العام).

المبدأ: كل ما أغلق السعر قريباً من أعلى الشمعة، افترضنا أن أغلب حجمها
كان ضغط شراء. كل ما أغلق قريباً من أدنى الشمعة، افترضنا العكس.
"""
import pandas as pd
import numpy as np


def close_location_value(row) -> float:
    """
    يحسب موقع الإغلاق لشمعة واحدة (للاستخدام المفرد مثلاً مع df.iloc[-1])
    """
    rng = row["high"] - row["low"]
    if rng == 0:
        return 0.5
    return (row["close"] - row["low"]) / rng


def estimate_buy_sell_volume(df: pd.DataFrame) -> pd.DataFrame:
    """
    يضيف أعمدة تقديرية لحجم الشراء والبيع باستخدام الحسابات المتجهة السريعة (Vectorized)
    """
    result = df.copy()
    
    rng = result["high"] - result["low"]
    
    # حساب CLV بشكل متجه وسريع مع الحماية من القسمة على الصفر
    clv = np.where(rng == 0, 0.5, (result["close"] - result["low"]) / rng)

    result["clv"] = clv
    result["buy_volume"] = result["volume"] * clv
    result["sell_volume"] = result["volume"] * (1 - clv)
    result["delta"] = result["buy_volume"] - result["sell_volume"]

    return result


def calc_cvd(df: pd.DataFrame) -> pd.Series:
    """يحسب CVD كمجموع تراكمي لـ Delta عبر الزمن"""
    if df is None or df.empty or "volume" not in df.columns:
        return pd.Series(dtype=float)
        
    enriched = estimate_buy_sell_volume(df)
    return enriched["delta"].cumsum()


def cvd_trend(df: pd.DataFrame, lookback: int = 10) -> str:
    """
    يحدد اتجاه CVD الأخير (هل ضغط الشراء التراكمي يتزايد أم يتناقص)
    يعيد: "شراء متزايد" / "بيع متزايد" / "متوازن"
    """
    if df is None or len(df) < lookback + 1:
        return "غير محدد"

    cvd = calc_cvd(df)
    if cvd.empty:
        return "غير محدد"

    recent_change = cvd.iloc[-1] - cvd.iloc[-lookback]
    avg_volume = df["volume"].iloc[-lookback:].mean()

    if avg_volume == 0 or np.isnan(avg_volume):
        return "غير محدد"

    # نسبة التغير مقارنة بمتوسط الحجم لتطبيع القيمة
    normalized_change = recent_change / (avg_volume * lookback)

    if normalized_change > 0.05:
        return "شراء متزايد"
    elif normalized_change < -0.05:
        return "بيع متزايد"
    return "متوازن"


def detect_cvd_divergence(df: pd.DataFrame, lookback: int = 30, order: int = 3):
    """
    يفحص دايفرجنس بين السعر وCVD لتبين ضعف ضغط الشراء/البيع
    """
    if df is None or len(df) < lookback:
        return None

    try:
        from divergence import detect_divergence
        cvd = calc_cvd(df)
        return detect_divergence(df, cvd, lookback=lookback, order=order)
    except Exception:
        # في حال عدم وجود الموديول أو وجود اختلاف بداخل دالة detect_divergence
        return None


def analyze_cvd(df: pd.DataFrame) -> dict:
    """يجمع كل تحليلات CVD بمكان واحد لدمجها بسهولة بباقي طبقات التحليل"""
    if df is None or df.empty:
        return {
            "trend": "غير محدد",
            "divergence": None,
            "last_clv": 0.5,
        }

    return {
        "trend": cvd_trend(df),
        "divergence": detect_cvd_divergence(df),
        "last_clv": round(close_location_value(df.iloc[-1]), 3),
    }
