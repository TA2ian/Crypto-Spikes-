from __future__ import annotations

from typing import Sequence

from .enums import PivotType
from .models import Pivot


def detect_pivots(
    prices: Sequence[float],
    indicator: Sequence[float],
    *,
    left: int = 2,
    right: int = 2,
) -> list[Pivot]:
    """
    Detect local highs and lows in price and pair them with
    the corresponding indicator values.
    """

    if len(prices) != len(indicator):
        raise ValueError(
            "prices and indicator must have equal length"
        )

    if len(prices) < left + right + 1:
        return []

    if left < 1 or right < 1:
        raise ValueError(
            "left and right must be >= 1"
        )

    pivots: list[Pivot] = []

    for index in range(
        left,
        len(prices) - right,
    ):
        current = prices[index]

        left_values = prices[
            index - left:index
        ]

        right_values = prices[
            index + 1:index + right + 1
        ]

        is_high = all(
            current > value
            for value in (*left_values, *right_values)
        )

        is_low = all(
            current < value
            for value in (*left_values, *right_values)
        )

        if is_high:
            pivots.append(
                Pivot(
                    index=index,
                    price=current,
                    indicator_value=indicator[index],
                    pivot_type=PivotType.HIGH,
                )
            )

        elif is_low:
            pivots.append(
                Pivot(
                    index=index,
                    price=current,
                    indicator_value=indicator[index],
                    pivot_type=PivotType.LOW,
                )
            )

    return pivots
