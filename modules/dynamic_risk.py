import pandas as pd

def calculate_atr(df: pd.DataFrame, period: int = 14) -> float:
    """حساب متوسط التذبذب الحقيقي (ATR)"""
    high = df['high']
    low = df['low']
    close = df['close'].shift(1)
    
    tr = pd.concat([
        high - low,
        (high - close).abs(),
        (low - close).abs()
    ], axis=1).max(axis=1)
    
    atr = tr.rolling(period).mean().iloc[-1]
    return float(atr) if not pd.isna(atr) else 0.0

def calculate_dynamic_targets(entry_price: float, atr: float, direction: str = "LONG"):
    """حساب الأهداف والستوب لوز بناءً على ATR"""
    if atr == 0:
        atr = entry_price * 0.02
        
    if direction == "LONG":
        stop_loss = entry_price - (atr * 1.5)
        target1 = entry_price + (atr * 2.0)
        target2 = entry_price + (atr * 3.5)
    else:
        stop_loss = entry_price + (atr * 1.5)
        target1 = entry_price - (atr * 2.0)
        target2 = entry_price - (atr * 3.5)
        
    return stop_loss, target1, target2

def rate_signal_confidence(has_confluence: bool, fvg: dict | None, is_sweep: bool) -> str:
    """تقييم الإشارة بالنجوم"""
    stars = 2
    if has_confluence: stars += 1
    if fvg: stars += 1
    if is_sweep: stars += 1
    return "⭐" * min(stars, 5)
