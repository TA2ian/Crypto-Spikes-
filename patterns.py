"""
أنماط الشموع الكلاسيكية + Order Blocks متقدمة مع FVG & BOS (SMC Framework)
يقوم هذا الملف بفرز وتحليل منطق المال الذكي وتأكيد الأنماط بحجم التداول.
"""
import pandas as pd
import numpy as np


# ============ أنماط الشموع ============

def candle_range(row) -> float:
    return row["high"] - row["low"]


def body_size(row) -> float:
    return abs(row["close"] - row["open"])


def is_volume_confirmed(df: pd.DataFrame, index: int = -2, multiplier: float = 1.2) -> bool:
    """تتأكد من وجود سيولة وحجم تداول يدعم الشمعة المحددة"""
    if "volume" not in df.columns or len(df) < 15:
        return True
    avg_vol = df["volume"].iloc[-15:-2].mean()
    return (df["volume"].iloc[index] >= avg_vol * multiplier) if avg_vol > 0 else True


def detect_candle_patterns(df: pd.DataFrame, use_closed: bool = True) -> list[dict]:
    """
    تكتشف الأنماط الانعكاسية المكتملة وتدمج تأكيد حجم التداول
    """
    found = []
    if len(df) < 3:
        return found

    idx = -2 if use_closed else -1
    last = df.iloc[idx]
    prev = df.iloc[idx - 1]

    rng = candle_range(last)
    body = body_size(last)
    vol_ok = is_volume_confirmed(df, index=idx)

    if rng == 0:
        return found

    # 1. الابتلاع الصعودي
    if prev["close"] < prev["open"] and last["close"] > last["open"]:
        if last["open"] <= prev["close"] and last["close"] >= prev["open"]:
            found.append({
                "pattern": "ابتلاع صعودي",
                "direction": "LONG",
                "volume_confirmed": vol_ok
            })

    # 2. الابتلاع الهبوطي
    elif prev["close"] > prev["open"] and last["close"] < last["open"]:
        if last["open"] >= prev["close"] and last["close"] <= prev["open"]:
            found.append({
                "pattern": "ابتلاع هبوطي",
                "direction": "SHORT",
                "volume_confirmed": vol_ok
            })

    # 3. المطرقة
    lower_wick = min(last["open"], last["close"]) - last["low"]
    upper_wick = last["high"] - max(last["open"], last["close"])
    
    if lower_wick >= body * 2.0 and upper_wick <= body * 0.5 and (body / rng) < 0.35:
        found.append({
            "pattern": "مطرقة (ارتداد صعودي)",
            "direction": "LONG",
            "volume_confirmed": vol_ok
        })

    return found


# ============ SMC: Order Blocks & FVG & BOS ============

def detect_fvg_after_candle(df: pd.DataFrame, candle_idx: int, direction: str) -> bool:
    """تكتشف وجود Fair Value Gap (FVG) بعد شمعة الـ OB مباشرة"""
    if candle_idx + 2 >= len(df):
        return False

    if direction == "bullish":
        return df.iloc[candle_idx + 2]["low"] > df.iloc[candle_idx]["high"]
    else:
        return df.iloc[candle_idx + 2]["high"] < df.iloc[candle_idx]["low"]


def find_advanced_order_block(df: pd.DataFrame, direction: str = "bullish", lookback: int = 25) -> dict | None:
    """
    يبحث عن Order Block متقدم بمعايير SMC عالية الجودة:
    1. حركة اندفاعية قوية
    2. عدم استهلاك المنطقة (Unmitigated)
    3. فحص وجود FVG مترافق
    4. فحص كسر بنية السوق (BOS)
    """
    if df is None or len(df) < lookback + 5:
        return None

    window = df.iloc[-(lookback + 5):-1].reset_index(drop=True)

    for i in range(len(window) - 4, 0, -1):
        candle = window.iloc[i]
        is_bear = candle["close"] < candle["open"]
        is_bull = candle["close"] > candle["open"]

        if direction == "bullish" and not is_bear:
            continue
        if direction == "bearish" and not is_bull:
            continue

        future = window.iloc[i + 1:]
        if future.empty:
            continue

        # قياس مدى قوة الحركة بعد الشمعة
        if direction == "bullish":
            max_move = (future["close"].max() - candle["close"]) / candle["close"]
            if max_move < 0.025: # الحد الأدنى للصعود 2.5%
                continue

            ob_low, ob_high = float(candle["low"]), float(candle["high"])
            # التأكد أن المنطقة غير مستهلكة
            if (future["close"] < ob_low).any():
                continue

            # تقييم الـ Confluence
            has_fvg = detect_fvg_after_candle(window, i, "bullish")
            recent_peak = window.iloc[max(0, i - 10):i]["high"].max()
            has_bos = (future["close"] > recent_peak).any()

            score = 1.0 + (1.5 if has_fvg else 0.0) + (1.5 if has_bos else 0.0)

            return {
                "type": "Bullish OB",
                "zone": (ob_low, ob_high),
                "has_fvg": has_fvg,
                "has_bos": has_bos,
                "quality_score": score,
            }

        elif direction == "bearish":
            max_move = (candle["close"] - future["close"].min()) / candle["close"]
            if max_move < 0.025:
                continue

            ob_low, ob_high = float(candle["low"]), float(candle["high"])
            if (future["close"] > ob_high).any():
                continue

            has_fvg = detect_fvg_after_candle(window, i, "bearish")
            recent_trough = window.iloc[max(0, i - 10):i]["low"].min()
            has_bos = (future["close"] < recent_trough).any()

            score = 1.0 + (1.5 if has_fvg else 0.0) + (1.5 if has_bos else 0.0)

            return {
                "type": "Bearish OB",
                "zone": (ob_low, ob_high),
                "has_fvg": has_fvg,
                "has_bos": has_bos,
                "quality_score": score,
            }

    return None
