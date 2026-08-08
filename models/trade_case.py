"""
Trade case domain model.

TradeCase represents the lifecycle of a trading opportunity from
pre-entry through closure.

It does not execute orders. Execution remains outside the domain model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class TradeState(str, Enum):
    WAITING = "waiting"
    READY = "ready"
    ENTRY = "entry"
    ACTIVE = "active"
    PARTIAL_TP = "partial_tp"
    TRAILING = "trailing"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class EntryType(str, Enum):
    FIRST_ENTRY = "first_entry"
    RETEST = "retest"
    RE_ENTRY = "re_entry"


@dataclass(slots=True)
class TradeCase:
    """
    Represents one trading case and its lifecycle.

    Structural targets are intentionally stored as immutable-after-entry
    values through the lifecycle methods below.
    """

    symbol: str
    direction: str

    entry_price: float

    stop_loss: float

    tp1: float | None = None
    tp2: float | None = None
    tp3: float | None = None
    tp4: float | None = None
    macro_target: float | None = None

    state: TradeState = TradeState.WAITING
    entry_type: EntryType = EntryType.FIRST_ENTRY

    strategy: str | None = None

    decision_id: str | None = None

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    activated_at: datetime | None = None
    closed_at: datetime | None = None

    trade_id: str | None = None

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.symbol = self.symbol.strip().upper()
        self.direction = self.direction.strip().lower()

        if not self.symbol:
            raise ValueError("symbol cannot be empty")

        if self.entry_price <= 0:
            raise ValueError(
                "entry_price must be greater than zero"
            )

        if self.stop_loss <= 0:
            raise ValueError(
                "stop_loss must be greater than zero"
            )

        if self.trade_id is None:
            self.trade_id = self._generate_trade_id()

        self._validate_targets()

    def _generate_trade_id(self) -> str:
        timestamp = self.created_at.strftime("%Y%m%d%H%M%S")
        return f"{self.symbol}-{timestamp}"

    def _validate_targets(self) -> None:
        targets = [
            self.tp1,
            self.tp2,
            self.tp3,
            self.tp4,
            self.macro_target,
        ]

        for index, target in enumerate(targets, start=1):
            if target is not None and target <= 0:
                raise ValueError(
                    f"TP target {index} must be greater than zero"
                )

    def activate(self) -> None:
        """
        Activate the trade.

        Once activated, structural targets must remain fixed.
        """

        if self.state not in {
            TradeState.READY,
            TradeState.ENTRY,
        }:
            raise ValueError(
                f"cannot activate trade from state {self.state.value}"
            )

        self.state = TradeState.ACTIVE
        self.activated_at = datetime.now(timezone.utc)

    def mark_ready(self) -> None:
        """Move a waiting case into READY state."""

        if self.state != TradeState.WAITING:
            raise ValueError(
                "only WAITING trades can become READY"
            )

        self.state = TradeState.READY

    def mark_entry(self) -> None:
        """Mark the trade as entering the market."""

        if self.state != TradeState.READY:
            raise ValueError(
                "only READY trades can enter"
            )

        self.state = TradeState.ENTRY

    def mark_partial_tp(self) -> None:
        """Record partial take-profit execution."""

        if self.state != TradeState.ACTIVE:
            raise ValueError(
                "partial TP requires an ACTIVE trade"
            )

        self.state = TradeState.PARTIAL_TP

    def start_trailing(self) -> None:
        """Start trailing-stop management."""

        if self.state not in {
            TradeState.ACTIVE,
            TradeState.PARTIAL_TP,
        }:
            raise ValueError(
                "trailing requires an ACTIVE or PARTIAL_TP trade"
            )

        self.state = TradeState.TRAILING

    def close(self) -> None:
        """Close the trade case."""

        if self.state in {
            TradeState.CLOSED,
            TradeState.CANCELLED,
        }:
            raise ValueError(
                "trade is already finalized"
            )

        self.state = TradeState.CLOSED
        self.closed_at = datetime.now(timezone.utc)

    def cancel(self) -> None:
        """Cancel the trade before final execution."""

        if self.state in {
            TradeState.ACTIVE,
            TradeState.PARTIAL_TP,
            TradeState.TRAILING,
            TradeState.CLOSED,
        }:
            raise ValueError(
                "active or completed trades cannot be cancelled"
            )

        self.state = TradeState.CANCELLED
        self.closed_at = datetime.now(timezone.utc)

    def can_change_targets(self) -> bool:
        """
        Return whether structural targets may still be changed.

        After ENTRY/ACTIVE, targets are considered locked.
        """

        return self.state in {
            TradeState.WAITING,
            TradeState.READY,
        }

    def update_targets(
        self,
        *,
        tp1: float | None = None,
        tp2: float | None = None,
        tp3: float | None = None,
        tp4: float | None = None,
        macro_target: float | None = None,
    ) -> None:
        """
        Update structural targets before activation.

        This deliberately refuses target movement after the trade
        enters the market.
        """

        if not self.can_change_targets():
            raise ValueError(
                "structural targets are locked after entry"
            )

        new_targets = [
            tp1,
            tp2,
            tp3,
            tp4,
            macro_target,
        ]

        for index, target in enumerate(new_targets, start=1):
            if target is not None and target <= 0:
                raise ValueError(
                    f"target {index} must be greater than zero"
                )

        if tp1 is not None:
            self.tp1 = tp1

        if tp2 is not None:
            self.tp2 = tp2

        if tp3 is not None:
            self.tp3 = tp3

        if tp4 is not None:
            self.tp4 = tp4

        if macro_target is not None:
            self.macro_target = macro_target

    def is_active(self) -> bool:
        """Return whether the trade is currently active."""

        return self.state in {
            TradeState.ENTRY,
            TradeState.ACTIVE,
            TradeState.PARTIAL_TP,
            TradeState.TRAILING,
        }
