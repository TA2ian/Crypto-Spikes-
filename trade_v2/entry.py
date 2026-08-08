from __future__ import annotations

from .enums import EntryType, TradeStatus
from .models import (
    TradeEntry,
    TradeState,
)


def register_entry(
    trade: TradeState,
    *,
    price: float,
    entry_type: EntryType,
) -> TradeEntry:

    if trade.status == TradeStatus.CLOSED:
        raise ValueError(
            "Cannot enter a closed trade."
        )

    if trade.status == TradeStatus.INVALIDATED:
        raise ValueError(
            "Cannot enter an invalidated trade."
        )

    entry = TradeEntry(
        price=price,
        entry_type=entry_type,
    )

    trade.entries.append(entry)

    trade.active_entry_count += 1

    trade.status = TradeStatus.ACTIVE

    return entry
