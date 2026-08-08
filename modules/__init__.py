
"""
Domain models for Halal Crypto Intelligence V2.

This package contains the canonical data structures used by
the V2 decision and trading architecture.
"""

from .asset_profile import (
    AssetProfile,
    HalalStatus,
    LiquidityState,
    MarketRegime,
    MarketType,
    StructuralBias,
    TrendDirection,
    VolatilityState,
)

from .market_context import (
    MarketContext,
    RiskRegime,
    TradingSession,
)

from .evidence import (
    Evidence,
    EvidenceDirection,
    EvidenceType,
    DivergenceType,
)

from .decision import (
    Decision,
    DecisionAction,
    RiskLevel,
)

from .trade_case import (
    EntryType,
    TradeCase,
    TradeState,
)

__all__ = [
    "AssetProfile",
    "HalalStatus",
    "LiquidityState",
    "MarketRegime",
    "MarketType",
    "StructuralBias",
    "TrendDirection",
    "VolatilityState",
    "MarketContext",
    "RiskRegime",
    "TradingSession",
    "Evidence",
    "EvidenceDirection",
    "EvidenceType",
    "DivergenceType",
    "Decision",
    "DecisionAction",
    "RiskLevel",
    "EntryType",
    "TradeCase",
    "TradeState",
]
