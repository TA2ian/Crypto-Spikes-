from __future__ import annotations

from collections.abc import Sequence

from .enums import (
    DivergenceDirection,
    DivergenceType,
    PivotType,
    IndicatorType,
)
from .models import DivergenceSignal, Pivot


def _relative_difference(a: float, b: float) -> float:
    denominator = max(abs(a), abs(b), 1e-12)
    return abs(a - b) / denominator


def detect_regular(
    first: Pivot,
    second: Pivot,
    *,
    indicator: IndicatorType,
    timeframe: str,
) -> DivergenceSignal | None:

    if first.pivot_type == PivotType.LOW:
        if (
            second.price < first.price
            and second.indicator_value > first.indicator_value
        ):
            strength = min(
                1.0,
                (
                    _relative_difference(
                        first.price,
                        second.price,
                    )
                    +
                    _relative_difference(
                        first.indicator_value,
                        second.indicator_value,
                    )
                ) / 2,
            )

            return DivergenceSignal(
                divergence_type=DivergenceType.REGULAR,
                direction=DivergenceDirection.BULLISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=strength,
                reliability=0.80,
            )

    if first.pivot_type == PivotType.HIGH:
        if (
            second.price > first.price
            and second.indicator_value < first.indicator_value
        ):
            strength = min(
                1.0,
                (
                    _relative_difference(
                        first.price,
                        second.price,
                    )
                    +
                    _relative_difference(
                        first.indicator_value,
                        second.indicator_value,
                    )
                ) / 2,
            )

            return DivergenceSignal(
                divergence_type=DivergenceType.REGULAR,
                direction=DivergenceDirection.BEARISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=strength,
                reliability=0.80,
            )

    return None


def detect_hidden(
    first: Pivot,
    second: Pivot,
    *,
    indicator: IndicatorType,
    timeframe: str,
) -> DivergenceSignal | None:

    if first.pivot_type == PivotType.LOW:
        if (
            second.price > first.price
            and second.indicator_value < first.indicator_value
        ):
            return DivergenceSignal(
                divergence_type=DivergenceType.HIDDEN,
                direction=DivergenceDirection.BULLISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=0.75,
                reliability=0.82,
            )

    if first.pivot_type == PivotType.HIGH:
        if (
            second.price < first.price
            and second.indicator_value > first.indicator_value
        ):
            return DivergenceSignal(
                divergence_type=DivergenceType.HIDDEN,
                direction=DivergenceDirection.BEARISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=0.75,
                reliability=0.82,
            )

    return None


def detect_exaggerated(
    first: Pivot,
    second: Pivot,
    *,
    indicator: IndicatorType,
    timeframe: str,
    price_tolerance: float = 0.002,
) -> DivergenceSignal | None:

    price_difference = _relative_difference(
        first.price,
        second.price,
    )

    if price_difference > price_tolerance:
        return None

    if first.pivot_type == PivotType.LOW:
        if second.indicator_value > first.indicator_value:
            return DivergenceSignal(
                divergence_type=DivergenceType.EXAGGERATED,
                direction=DivergenceDirection.BULLISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=0.70,
                reliability=0.76,
            )

    if first.pivot_type == PivotType.HIGH:
        if second.indicator_value < first.indicator_value:
            return DivergenceSignal(
                divergence_type=DivergenceType.EXAGGERATED,
                direction=DivergenceDirection.BEARISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second),
                strength=0.70,
                reliability=0.76,
            )

    return None


def detect_triple(
    pivots: Sequence[Pivot],
    *,
    indicator: IndicatorType,
    timeframe: str,
) -> DivergenceSignal | None:

    if len(pivots) < 3:
        return None

    first, second, third = pivots[-3:]

    if not (
        first.pivot_type
        == second.pivot_type
        == third.pivot_type
    ):
        return None

    if first.pivot_type == PivotType.LOW:

        price_pattern = (
            third.price <= second.price
            and second.price <= first.price
        )

        indicator_pattern = (
            third.indicator_value >= second.indicator_value
            and second.indicator_value >= first.indicator_value
        )

        if price_pattern and indicator_pattern:
            return DivergenceSignal(
                divergence_type=DivergenceType.TRIPLE,
                direction=DivergenceDirection.BULLISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second, third),
                strength=0.90,
                reliability=0.88,
            )

    if first.pivot_type == PivotType.HIGH:

        price_pattern = (
            third.price >= second.price
            and second.price >= first.price
        )

        indicator_pattern = (
            third.indicator_value <= second.indicator_value
            and second.indicator_value <= first.indicator_value
        )

        if price_pattern and indicator_pattern:
            return DivergenceSignal(
                divergence_type=DivergenceType.TRIPLE,
                direction=DivergenceDirection.BEARISH,
                indicator=indicator,
                timeframe=timeframe,
                pivots=(first, second, third),
                strength=0.90,
                reliability=0.88,
            )

    return None
