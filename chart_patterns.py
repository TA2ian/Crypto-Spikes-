"""
كشف النماذج السعرية الكلاسيكية: قاع/قمة مزدوجة، رأس وكتفين، مثلثات،
علم (Flag)، قناة سعرية، واتجاه عام (Trend).

ملاحظة منهجية: هذه أنماط بصرية بطبيعتها، وخوارزميات كشفها الآلي تحتمل
نسبة إشارات كاذبة أعلى من المؤشرات الرياضية البحتة (RSI، فيبوناتشي).
تُعامل هنا كطبقة معلوماتية تحتاج تأكيد العين البشرية دائماً.
"""
"""
كشف النماذج السعرية الكلاسيكية: قاع/قمة مزدوجة، رأس وكتفين، مثلثات،
علم (Flag)، قناة سعرية، واتجاه عام (Trend).

ملاحظة منهجية: هذه أنماط بصرية بطبيعتها، وخوارزميات كشفها الآلي تحتمل
نسبة إشارات كاذبة أعلى من المؤشرات الرياضية البحتة (RSI، فيبوناتشي).
تُعامل هنا كطبقة معلوماتية تحتاج تأكيد العين البشرية دائماً.
"""   
"""
كشف النماذج السعرية الكلاسيكية: قاع/قمة مزدوجة، رأس وكتفين، مثلثات،
علم (Flag)، قناة سعرية، واتجاه عام (Trend).

ملاحظة منهجية: هذه أنماط بصرية بطبيعتها، وخوارزميات كشفها الآلي تحتمل
نسبة إشارات كاذبة أعلى من المؤشرات الرياضية البحتة (RSI، فيبوناتشي).
تُعامل هنا كطبقة معلوماتية تحتاج تأكيد العين البشرية دائماً.
"""

"""
كشف النماذج السعرية المتقدم المعتمد على الأحجام والانحدار الخطي.
يوفر مستهدفات خروج ودخول دقيقة للنماذج.
"""
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
from divergence import find_local_extrema


def _calculate_linear_slope(series: pd.Series) -> tuple[float, float]:
    """حساب الميل ومعامل الاتساق R-Squared للانحدار الخطي"""
    x = np.arange(len(series))
    y = series.values
    if len(y) < 2:
        return 0.0, 0.0
    
    slope, intercept = np.polyfit(x, y, 1)
    
    # حساب R-Squared لتقييم مدى دقة واستقامة الخط
    y_pred = slope * x + intercept
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    ss_res = np.sum((y - y_pred) ** 2)
    r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    
    return float(slope), float(r_squared)


def detect_double_pattern_advanced(df: pd.DataFrame, lookback: int = 40, order: int = 3) -> Optional[Dict[str, Any]]:
    """
    يكشف القمة/القاع المزدوج مع فحص الحجم وتحديد سعر الكسر والهدف.
    """
    if len(df) < lookback:
        return None

    window = df.iloc[-lookback:].reset_index(drop=True)
    lows, highs = find_local_extrema(window["close"], order=order)
    has_volume = "volume" in window.columns

    # قمة مزدوجة
    if len(highs) >= 2:
        h1, h2 = highs[-2], highs[-1]
        p1, p2 = window["close"].iloc[h1], window["close"].iloc[h2]
        
        if abs(p1 - p2) / p1 <= 0.015:
            mid_lows = [l for l in lows if h1 < l < h2]
            if mid_lows:
                neckline = window["close"].iloc[mid_lows].min()
                height = max(p1, p2) - neckline
                
                # تأكيد الحجم: حجم القمة الأولى أعلى من الثانية
                vol_confirmed = True
                if has_volume:
                    vol_confirmed = window["volume"].iloc[h1] > window["volume"].iloc[h2]
                
                if vol_confirmed and (height / p1 >= 0.008):
                    return {
                        "pattern": "قمة مزدوجة",
                        "neckline": round(neckline, 4),
                        "target": round(neckline - height, 4),
                        "stop_loss": round(max(p1, p2), 4),
                        "confirmed_by_volume": vol_confirmed
                    }

    # قاع مزدوج
    if len(lows) >= 2:
        l1, l2 = lows[-2], lows[-1]
        p1, p2 = window["close"].iloc[l1], window["close"].iloc[l2]
        
        if abs(p1 - p2) / p1 <= 0.015:
            mid_highs = [h for h in highs if l1 < h < l2]
            if mid_highs:
                neckline = window["close"].iloc[mid_highs].max()
                height = neckline - min(p1, p2)
                
                vol_confirmed = True
                if has_volume:
                    vol_confirmed = window["volume"].iloc[l1] > window["volume"].iloc[l2]
                
                if vol_confirmed and (height / p1 >= 0.008):
                    return {
                        "pattern": "قاع مزدوج",
                        "neckline": round(neckline, 4),
                        "target": round(neckline + height, 4),
                        "stop_loss": round(min(p1, p2), 4),
                        "confirmed_by_volume": vol_confirmed
                    }

    return None


def detect_flag_advanced(df: pd.DataFrame, pole_lookback: int = 15, flag_lookback: int = 8) -> Optional[Dict[str, Any]]:
    """
    يكشف نموذج العلم بدقة عالية مع حساب أحجام التداول في العمود والعلم
    """
    total_needed = pole_lookback + flag_lookback
    if len(df) < total_needed:
        return None

    pole_df = df.iloc[-total_needed:-flag_lookback]
    flag_df = df.iloc[-flag_lookback:]

    pole_move = (pole_df["close"].iloc[-1] - pole_df["close"].iloc[0]) / pole_df["close"].iloc[0]
    flag_range = (flag_df["high"].max() - flag_df["low"].min()) / flag_df["close"].mean()

    # شروط النسبة
    is_tight = flag_range < abs(pole_move) * 0.45
    has_volume = "volume" in df.columns
    
    vol_ratio = 1.0
    if has_volume and pole_df["volume"].mean() > 0:
        # فحص هل انخفض حجم التداول أثناء تشكل العلم؟
        vol_ratio = flag_df["volume"].mean() / pole_df["volume"].mean()

    vol_confirmed = vol_ratio < 0.8 if has_volume else True

    current_price = flag_df["close"].iloc[-1]
    pole_height = abs(pole_df["close"].iloc[-1] - pole_df["close"].iloc[0])

    if pole_move >= 0.04 and is_tight and vol_confirmed:
        return {
            "pattern": "علم صاعد",
            "breakout_level": round(flag_df["high"].max(), 4),
            "target": round(current_price + pole_height, 4),
            "stop_loss": round(flag_df["low"].min(), 4),
            "confirmed_by_volume": vol_confirmed
        }

    if pole_move <= -0.04 and is_tight and vol_confirmed:
        return {
            "pattern": "علم هابط",
            "breakout_level": round(flag_df["low"].min(), 4),
            "target": round(current_price - pole_height, 4),
            "stop_loss": round(flag_df["high"].max(), 4),
            "confirmed_by_volume": vol_confirmed
        }

    return None


def detect_all_patterns_advanced(df: pd.DataFrame) -> Dict[str, Any]:
    """تجميع وتجميع النتائج المتقدمة مع بيانات الدخول والخروج"""
    if df is None or df.empty or len(df) < 15:
        return {}

    results = {
        "double_pattern": detect_double_pattern_advanced(df),
        "flag": detect_flag_advanced(df),
    }
    
    # تنظيف القاموس من القيم الفارغة None
    return {k: v for k, v in results.items() if v is not None}
