"""
Market context domain model.

MarketContext describes the environment in which an asset is being
evaluated. It prevents individual strategies from independently
reconstructing the global market state.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class RiskRegime(str, Enum):
    RISK_ON = "risk_on"
    NEUTRAL = "neutral"
    RISK_OFF = "risk_off"
    EXTREME_RISK_OFF = "extreme_risk_off"
    UNKNOWN = "unknown"


class TradingSession(str, Enum):
    ASIA = "asia"
    LONDON = "london"
    NEW_YORK = "new_york"
    OVERLAP = "overlap"
    OFF_SESSION = "off_session"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class MarketContext:
    """
    Snapshot of global market conditions at analysis time.
    """

    btc_trend: str = "unknown"

    btc_dominance: float | None = None
    usdt_dominance: float | None = None

    fear_greed_index: float | None = None
    market_volatility: float | None = None

    macro_trend: str = "unknown"
    risk_regime: RiskRegime = RiskRegime.UNKNOWN
    session: TradingSession = TradingSession.UNKNOWN

    market_breadth: float | None = None

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.btc_trend = self.btc_trend.strip().lower()
        self.macro_trend = self.macro_trend.strip().lower()

        self._validate_percentage(
            self.btc_dominance,
            "btc_dominance",
        )

        self._validate_percentage(
            self.usdt_dominance,
            "usdt_dominance",
        )

        if self.fear_greed_index is not None:
            if not 0 <= self.fear_greed_index <= 100:
                raise ValueError(
                    "fear_greed_index must be between 0 and 100"
                )

        if self.market_breadth is not None:
            if not -1 <= self.market_breadth <= 1:
                raise ValueError(
                    "market_breadth must be between -1 and 1"
                )

        if self.market_volatility is not None:
            if self.market_volatility < 0:
                raise ValueError(
                    "market_volatility cannot be negative"
                )

    @staticmethod
    def _validate_percentage(
        value: float | None,
        field_name: str,
    ) -> None:
        if value is None:
            return

        if not 0 <= value <= 100:
            raise ValueError(
                f"{field_name} must be between 0 and 100"
            )

    def update(
        self,
        *,
        btc_trend: str | None = None,
        btc_dominance: float | None = None,
        usdt_dominance: float | None = None,
        fear_greed_index: float | None = None,
        market_volatility: float | None = None,
        macro_trend: str | None = None,
        risk_regime: RiskRegime | None = None,
        session: TradingSession | None = None,
        market_breadth: float | None = None,
    ) -> None:
        """Update the market context snapshot."""

        if btc_trend is not None:
            self.btc_trend = btc_trend.strip().lower()

        if btc_dominance is not None:
            self._validate_percentage(
                btc_dominance,
                "btc_dominance",
            )
            self.btc_dominance = btc_dominance

        if usdt_dominance is not None:
            self._validate_percentage(
                usdt_dominance,
                "usdt_dominance",
            )
            self.usdt_dominance = usdt_dominance

        if fear_greed_index is not None:
            if not 0 <= fear_greed_index <= 100:
                raise ValueError(
                    "fear_greed_index must be between 0 and 100"
                )
            self.fear_greed_index = fear_greed_index

        if market_volatility is not None:
            if market_volatility < 0:
                raise ValueError(
                    "market_volatility cannot be negative"
                )
            self.market_volatility = market_volatility

        if macro_trend is not None:
            self.macro_trend = macro_trend.strip().lower()

        if risk_regime is not None:
            self.risk_regime = risk_regime

        if session is not None:
            self.session = session

        if market_breadth is not None:
            if not -1 <= market_breadth <= 1:
                raise ValueError(
                    "market_breadth must be between -1 and 1"
                )
            self.market_breadth = market_breadth

        self.timestamp = datetime.now(timezone.utc)

    def add_metadata(self, key: str, value: Any) -> None:
        """Add contextual metadata."""

        key = key.strip()

        if not key:
            raise ValueError("metadata key cannot be empty")

        self.metadata[key] = value
        self.timestamp = datetime.now(timezone.utc)
