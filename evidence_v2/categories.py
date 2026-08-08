from enum import Enum


class EvidenceCategory(str, Enum):
    TREND = "trend"
    STRUCTURE = "structure"
    LIQUIDITY = "liquidity"
    MOMENTUM = "momentum"
    VOLUME = "volume"
    VOLATILITY = "volatility"
    SMC = "smc"
    WYCKOFF = "wyckoff"
    DIVERGENCE = "divergence"
    SUPPORT_RESISTANCE = "support_resistance"
    PATTERN = "pattern"
    DOMINANCE = "dominance"
    SENTIMENT = "sentiment"


class EvidencePolarity(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class ConfluenceStrength(str, Enum):
    VERY_WEAK = "very_weak"
    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"
    VERY_STRONG = "very_strong"
