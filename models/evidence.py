"""
Evidence domain model.

Evidence represents an observable or derived market fact that can
contribute to a hypothesis or decision.

Evidence is NOT a decision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from typing import Any


class EvidenceType(str, Enum):
    TREND = "trend"
    STRUCTURE = "structure"
    LIQUIDITY_SWEEP = "liquidity_sweep"
    ORDER_BLOCK = "order_block"
    FVG = "fvg"
    DIVERGENCE = "divergence"
    VOLUME = "volume"
    MOMENTUM = "momentum"
    VOLATILITY = "volatility"
    SUPPORT = "support"
    RESISTANCE = "resistance"
    PATTERN = "pattern"
    DOMINANCE = "dominance"
    SENTIMENT = "sentiment"


class EvidenceDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class DivergenceType(str, Enum):
    REGULAR = "regular"
    HIDDEN = "hidden"
    EXAGGERATED = "exaggerated"
    TRIPLE = "triple"


@dataclass(slots=True)
class Evidence:
    """
    A single piece of market evidence.

    Strength, reliability and freshness are normalized to 0..1.
    """

    type: EvidenceType
    direction: EvidenceDirection

    strength: float
    timeframe: str
    source: str

    reliability: float = 1.0
    freshness: float = 1.0

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    evidence_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    subtype: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._validate_score(self.strength, "strength")
        self._validate_score(self.reliability, "reliability")
        self._validate_score(self.freshness, "freshness")

        self.timeframe = self.timeframe.strip()

        if not self.timeframe:
            raise ValueError("timeframe cannot be empty")

        self.source = self.source.strip()

        if not self.source:
            raise ValueError("source cannot be empty")

        if not self.evidence_id.strip():
            raise ValueError("evidence_id cannot be empty")

        if isinstance(self.subtype, DivergenceType):
            self.subtype = self.subtype.value

    @staticmethod
    def _validate_score(
        value: float,
        field_name: str,
    ) -> None:
        if not 0 <= value <= 1:
            raise ValueError(
                f"{field_name} must be between 0 and 1"
            )

    @property
    def quality(self) -> float:
        """
        Combined evidence quality.

        This is intentionally simple at the domain layer.
        The Evidence Engine may later use a more sophisticated model.
        """

        return (
            self.strength
            * self.reliability
            * self.freshness
        )

    @property
    def is_bullish(self) -> bool:
        return self.direction == EvidenceDirection.BULLISH

    @property
    def is_bearish(self) -> bool:
        return self.direction == EvidenceDirection.BEARISH

    def add_metadata(self, key: str, value: Any) -> None:
        """Attach additional evidence-specific information."""

        key = key.strip()

        if not key:
            raise ValueError("metadata key cannot be empty")

        self.metadata[key] = value

    def age_seconds(self) -> float:
        """Return evidence age in seconds."""

        now = datetime.now(timezone.utc)

        timestamp = self.timestamp

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        return max(
            0.0,
            (now - timestamp).total_seconds(),
        )

    def matches_direction(
        self,
        direction: EvidenceDirection,
    ) -> bool:
        """Check whether this evidence supports a given direction."""

        return self.direction == direction
