from enum import Enum


class DivergenceType(str, Enum):
    REGULAR = "regular"
    HIDDEN = "hidden"
    EXAGGERATED = "exaggerated"
    TRIPLE = "triple"


class DivergenceDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"


class PivotType(str, Enum):
    HIGH = "high"
    LOW = "low"


class IndicatorType(str, Enum):
    RSI = "rsi"
    MACD = "macd"
    STOCHASTIC = "stochastic"
    CVD = "cvd"
    CUSTOM = "custom"
