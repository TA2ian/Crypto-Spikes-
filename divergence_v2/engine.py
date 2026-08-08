from __future__ import annotations

from collections.abc import Sequence

from .detector import (
    detect_exaggerated,
    detect_hidden,
    detect_regular,
    detect_triple,
)
from .enums import IndicatorType
from .models import DivergenceSignal
from .pivots import detect_pivots


class DivergenceEngine:
    """
    High-level divergence analysis engine.

    It detects all supported divergence classes without making
    trading decisions.
    """

    def __init__(
        self,
        *,
        pivot_left: int = 1,
        pivot_right: int = 1,
        exaggerated_tolerance: float = 0.002,
    ) -> None:

        self.pivot_left = pivot_left
        self.pivot_right = pivot_right
        self.exaggerated_tolerance = exaggerated_tolerance

    def analyze(
        self,
        prices: Sequence[float],
        indicator_values: Sequence[float],
        *,
        indicator: IndicatorType,
        timeframe: str,
    ) -> list[DivergenceSignal]:

        pivots = detect_pivots(
            prices,
            indicator_values,
            left=self.pivot_left,
            right=self.pivot_right,
        )

        if len(pivots) < 2:
            return []

        signals: list[DivergenceSignal] = []

        # Do not assume the last two pivots form the relevant comparison.
        # A valid divergence may occur several pivots back and still be the
        # most recent confirmed structural relationship.
        for first_index, first in enumerate(pivots[:-1]):
            for second in pivots[first_index + 1:]:
                if first.pivot_type != second.pivot_type:
                    continue

                for detector in (detect_regular, detect_hidden):
                    signal = detector(
                        first,
                        second,
                        indicator=indicator,
                        timeframe=timeframe,
                    )

                    if signal is not None:
                        signals.append(signal)

                exaggerated = detect_exaggerated(
                    first,
                    second,
                    indicator=indicator,
                    timeframe=timeframe,
                    price_tolerance=self.exaggerated_tolerance,
                )

                if exaggerated is not None:
                    signals.append(exaggerated)

        # Triple divergence is evaluated on every consecutive group of
        # three pivots of the same type rather than only the last three
        # pivots in the complete mixed high/low sequence.
        for first_index in range(len(pivots) - 2):
            triple_candidates = pivots[
                first_index:first_index + 3
            ]

            if len({
                pivot.pivot_type
                for pivot in triple_candidates
            }) != 1:
                continue

            triple = detect_triple(
                triple_candidates,
                indicator=indicator,
                timeframe=timeframe,
            )

            if triple is not None:
                signals.append(triple)

        return self._deduplicate(signals)

    @staticmethod
    def _deduplicate(
        signals: list[DivergenceSignal],
    ) -> list[DivergenceSignal]:

        unique: dict[
            tuple[str, str, str, str],
            DivergenceSignal,
        ] = {}

        for signal in signals:
            key = (
                signal.divergence_type.value,
                signal.direction.value,
                signal.indicator.value,
                signal.timeframe,
            )

            existing = unique.get(key)

            if existing is None:
                unique[key] = signal
                continue

            if signal.strength > existing.strength:
                unique[key] = signal

        return list(unique.values())
