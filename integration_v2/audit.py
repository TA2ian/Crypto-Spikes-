from __future__ import annotations

from collections.abc import Iterable

from .models import AuditEvent


class AuditTrail:
    """
    In-memory audit trail.

    Persistent storage is intentionally deferred
    to a later integration stage.
    """

    def __init__(self) -> None:
        self._events: list[AuditEvent] = []

    def record(
        self,
        event: AuditEvent,
    ) -> AuditEvent:

        self._events.append(event)

        return event

    def events(
        self,
    ) -> tuple[AuditEvent, ...]:

        return tuple(self._events)

    def for_symbol(
        self,
        symbol: str,
    ) -> tuple[AuditEvent, ...]:

        symbol = symbol.strip().upper()

        return tuple(
            event
            for event in self._events
            if event.symbol == symbol
        )

    def extend(
        self,
        events: Iterable[AuditEvent],
    ) -> None:

        self._events.extend(events)
