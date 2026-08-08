from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Sequence


@dataclass(frozen=True, slots=True)
class ReplayEvent:
    timestamp: datetime
    payload: Any


@dataclass(frozen=True, slots=True)
class ReplayResult:
    processed: int
    outputs: tuple[Any, ...]
    rejected_future_events: int = 0


class HistoricalReplay:
    """
    Deterministic historical replay with a strict
    no-lookahead boundary.
    """

    def run(
        self,
        events: Sequence[ReplayEvent],
        callback: Callable[
            [ReplayEvent, tuple[ReplayEvent, ...]],
            Any,
        ],
    ) -> ReplayResult:

        ordered = sorted(
            events,
            key=lambda event: event.timestamp,
        )

        outputs: list[Any] = []

        for index, event in enumerate(ordered):

            history = tuple(
                ordered[:index]
            )

            # The callback receives:
            # - the current event
            # - previous events only
            #
            # Future events are never exposed.

            outputs.append(
                callback(
                    event,
                    history,
                )
            )

        return ReplayResult(
            processed=len(ordered),
            outputs=tuple(outputs),
        )
