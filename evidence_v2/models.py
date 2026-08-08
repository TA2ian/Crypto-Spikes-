from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .categories import (
    EvidenceCategory,
    EvidencePolarity,
)


@dataclass(frozen=True, slots=True)
class EvidenceRecord:
    """
    Normalized evidence consumed by the Confluence Engine.
    """

    category: EvidenceCategory
    polarity: EvidencePolarity

    name: str

    strength: float
    reliability: float
    freshness: float

    timeframe: str
    source: str

    evidence_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    weight: float = 1.0

    metadata: dict[str, object] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self._validate_score(
            self.strength,
            "strength",
        )

        self._validate_score(
            self.reliability,
            "reliability",
        )

        self._validate_score(
            self.freshness,
            "freshness",
        )

        if self.weight < 0:
            raise ValueError(
                "weight cannot be negative"
            )

        if not self.name.strip():
            raise ValueError(
                "evidence name cannot be empty"
            )

        if not self.timeframe.strip():
            raise ValueError(
                "timeframe cannot be empty"
            )

        if not self.source.strip():
            raise ValueError(
                "source cannot be empty"
            )

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
    def effective_score(self) -> float:
        return (
            self.strength
            * self.reliability
            * self.freshness
            * self.weight
        )
