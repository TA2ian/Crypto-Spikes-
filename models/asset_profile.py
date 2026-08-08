"""
Asset profile domain model.

An AssetProfile represents the identity and high-level market state
of an asset. It intentionally does not contain raw indicators such
as RSI, MACD, EMA, or ATR. Those belong to features/evidence layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Mapping


class MarketType(str, Enum):
    SPOT = "spot"
    PERPETUAL = "perpetual"
    FUTURES = "futures"
    UNKNOWN = "unknown"


class TrendDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    SIDEWAYS = "sideways"
    UNKNOWN = "unknown"


class StructuralBias(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"
    UNKNOWN = "unknown"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    ACCUMULATION = "accumulation"
    DISTRIBUTION = "distribution"
    HIGH_VOLATILITY = "high_volatility"
    LOW_VOLATILITY = "low_volatility"
    UNKNOWN = "unknown"


class VolatilityState(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


class LiquidityState(str, Enum):
    THIN = "thin"
    NORMAL = "normal"
    DEEP = "deep"
    UNKNOWN = "unknown"


class HalalStatus(str, Enum):
    APPROVED = "approved"
    REVIEW = "review"
    REJECTED = "rejected"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class AssetProfile:
    """
    Canonical identity and high-level state of a tradable asset.
    """

    symbol: str
    exchange: str

    market_type: MarketType = MarketType.UNKNOWN
    quote_asset: str = "USDT"

    timeframes: tuple[str, ...] = (
        "15m",
        "1h",
        "4h",
        "1d",
        "3d",
        "1w",
    )

    macro_trend: TrendDirection = TrendDirection.UNKNOWN
    structural_bias: StructuralBias = StructuralBias.UNKNOWN
    market_regime: MarketRegime = MarketRegime.UNKNOWN

    volatility_state: VolatilityState = VolatilityState.UNKNOWN
    liquidity_state: LiquidityState = LiquidityState.UNKNOWN

    halal_status: HalalStatus = HalalStatus.UNKNOWN
    watchlist_status: bool = True

    metadata: dict[str, Any] = field(default_factory=dict)

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.exchange = self.exchange.strip()

        if not self.symbol:
            raise ValueError("symbol cannot be empty")

        if not self.exchange:
            raise ValueError("exchange cannot be empty")

        if not self.quote_asset.strip():
            raise ValueError("quote_asset cannot be empty")

        if not self.timeframes:
            raise ValueError("at least one timeframe is required")

        self.timeframes = tuple(
            timeframe.strip()
            for timeframe in self.timeframes
            if timeframe and timeframe.strip()
        )

        if not self.timeframes:
            raise ValueError("timeframes cannot be empty")

    def update_state(
        self,
        *,
        macro_trend: TrendDirection | None = None,
        structural_bias: StructuralBias | None = None,
        market_regime: MarketRegime | None = None,
        volatility_state: VolatilityState | None = None,
        liquidity_state: LiquidityState | None = None,
    ) -> None:
        """
        Update high-level market state.

        Raw indicator values should NOT be passed here.
        """

        if macro_trend is not None:
            self.macro_trend = macro_trend

        if structural_bias is not None:
            self.structural_bias = structural_bias

        if market_regime is not None:
            self.market_regime = market_regime

        if volatility_state is not None:
            self.volatility_state = volatility_state

        if liquidity_state is not None:
            self.liquidity_state = liquidity_state

        self.updated_at = datetime.now(timezone.utc)

    def set_halal_status(self, status: HalalStatus) -> None:
        """Update the asset's halal classification status."""

        self.halal_status = status
        self.updated_at = datetime.now(timezone.utc)

    def set_watchlist_status(self, enabled: bool) -> None:
        """Enable or disable the asset on the watchlist."""

        self.watchlist_status = bool(enabled)
        self.updated_at = datetime.now(timezone.utc)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add or replace a metadata value."""

        key = key.strip()

        if not key:
            raise ValueError("metadata key cannot be empty")

        self.metadata[key] = value
        self.updated_at = datetime.now(timezone.utc)

    def is_tradeable(self) -> bool:
        """
        Return whether the asset is currently eligible for analysis/trading.

        This is intentionally conservative.
        """

        return (
            self.watchlist_status
            and self.halal_status == HalalStatus.APPROVED
        )
