from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .enums import (
    Direction,
    EntryType,
    ExitReason,
    TradeStatus,
)


@dataclass(frozen=True, slots=True)
class LockedTargets:
    entry: float
    stop_loss: float

    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    target_4: float | None = None

    locked_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass(frozen=True, slots=True)
class TradeEntry:
    price: float
    entry_type: EntryType

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )


@dataclass
class TradeState:
    direction: Direction

    status: TradeStatus

    targets: LockedTargets

    entries: list[TradeEntry] = field(
        default_factory=list
    )

    active_entry_count: int = 0

    remaining_quantity: float = 0.0

    realized_quantity: float = 0.0

    exit_reason: ExitReason | None = None

    trade_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    updated_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def targets_locked(self) -> bool:
        return True

    @property
    def active(self) -> bool:
        return self.status in {
            TradeStatus.ENTERED,
            TradeStatus.ACTIVE,
            TradeStatus.PARTIAL_TP,
            TradeStatus.TRAILING,
        }
