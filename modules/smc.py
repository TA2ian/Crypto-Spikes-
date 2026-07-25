import pandas as pd

def detect_fvg(df: pd.DataFrame) -> dict | None:
    """كشف الفجوات السعرية (Fair Value Gap - FVG)"""
    if len(df) < 3:
        return None
    
    c1_high = df.iloc[-3]['high']
    c3_low = df.iloc[-1]['low']
    
    if c3_low > c1_high:
        gap_size = ((c3_low - c1_high) / c1_high) * 100
        if gap_size >= 0.3:
            return {"type": "bullish_fvg", "top": c3_low, "bottom": c1_high, "size_pct": gap_size}
            
    return None

def detect_liquidity_sweep(df: pd.DataFrame, lookback: int = 15) -> bool:
    """كشف ضرب الستوبات وسحب السيولة (Liquidity Sweep)"""
    if len(df) < lookback + 1:
        return False
    
    recent_low = df['low'].iloc[-(lookback+1):-1].min()
    last_candle = df.iloc[-1]
    
    swept = last_candle['low'] < recent_low and last_candle['close'] > recent_low
    return swept
