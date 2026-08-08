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
        pivot_left: int = 2,
        pivot_right: int = 2,
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

        first = pivots[-2]
        second = pivots[-1]

        detectors = (
            detect_regular,
            detect_hidden,
        )

        for detector in detectors:
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

        triple = detect_triple(
            pivots,
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
