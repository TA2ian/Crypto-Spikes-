from __future__ import annotations

from .entry import register_entry
from .enums import (
    Direction,
    EntryType,
    ExitReason,
    TradeStatus,
)
from .lifecycle import (
    activate_trailing,
    close_trade,
    mark_partial_tp,
)
from .models import (
    TradeState,
)
from .targets import lock_targets


class TradeManager:

    def create_trade(
        self,
        *,
        direction: Direction,
        entry: float,
        stop_loss: float,
        target_1: float | None = None,
        target_2: float | None = None,
        target_3: float | None = None,
        target_4: float | None = None,
    ) -> TradeState:

        targets = lock_targets(
            entry=entry,
            stop_loss=stop_loss,
            target_1=target_1,
            target_2=target_2,
            target_3=target_3,
            target_4=target_4,
        )

        return TradeState(
            direction=direction,
            status=TradeStatus.READY,
            targets=targets,
        )

    def initial_entry(
        self,
        trade: TradeState,
        *,
        price: float,
    ):
        return register_entry(
            trade,
            price=price,
            entry_type=EntryType.INITIAL,
        )

    def retest_entry(
        self,
        trade: TradeState,
        *,
        price: float,
    ):
        return register_entry(
            trade,
            price=price,
            entry_type=EntryType.RETEST,
        )

    def reentry(
        self,
        trade: TradeState,
        *,
        price: float,
    ):
        return register_entry(
            trade,
            price=price,
            entry_type=EntryType.REENTRY,
        )

    def partial_tp(
        self,
        trade: TradeState,
    ) -> None:

        mark_partial_tp(trade)

    def trailing(
        self,
        trade: TradeState,
    ) -> None:

        activate_trailing(trade)

    def close(
        self,
        trade: TradeState,
        *,
        reason: ExitReason,
    ) -> None:

        close_trade(
            trade,
            reason=reason,
        )
