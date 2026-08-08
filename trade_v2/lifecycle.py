from __future__ import annotations

from datetime import datetime, timezone

from .enums import (
    ExitReason,
    TradeStatus,
)
from .models import TradeState


def mark_partial_tp(
    trade: TradeState,
) -> None:

    if not trade.active:
        raise ValueError(
            "Trade is not active."
        )

    trade.status = TradeStatus.PARTIAL_TP

    trade.updated_at = datetime.now(
        timezone.utc
    )


def activate_trailing(
    trade: TradeState,
) -> None:

    if not trade.active:
        raise ValueError(
            "Trade is not active."
        )

    trade.status = TradeStatus.TRAILING

    trade.updated_at = datetime.now(
        timezone.utc
    )


def close_trade(
    trade: TradeState,
    *,
    reason: ExitReason,
) -> None:

    if trade.status == TradeStatus.CLOSED:
        return

    trade.status = TradeStatus.CLOSED

    trade.exit_reason = reason

    trade.updated_at = datetime.now(
        timezone.utc
    )
