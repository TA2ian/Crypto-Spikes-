from __future__ import annotations

from dataclasses import dataclass, field

from .enums import (
    DivergenceDirection,
    DivergenceType,
    IndicatorType,
    PivotType,
)


@dataclass(frozen=True, slots=True)
class Pivot:
    index: int
    price: float
    indicator_value: float
    pivot_type: PivotType


@dataclass(frozen=True, slots=True)
class DivergenceSignal:
    divergence_type: DivergenceType
    direction: DivergenceDirection
    indicator: IndicatorType

    timeframe: str

    pivots: tuple[Pivot, ...]

    strength: float
    reliability: float

    metadata: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.strength <= 1:
            raise ValueError("strength must be between 0 and 1")

        if not 0 <= self.reliability <= 1:
            raise ValueError(
                "reliability must be between 0 and 1"
            )

        if len(self.pivots) < 2:
            raise ValueError(
                "a divergence requires at least two pivots"
            )

        if not self.timeframe.strip():
            raise ValueError(
                "timeframe cannot be empty"
            )
