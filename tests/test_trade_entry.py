from trade_v2 import (
    EntryType,
    TradeManager,
)


def test_initial_retest_and_reentry_are_distinguished() -> None:

    manager = TradeManager()

    trade = manager.create_trade(
        direction="long",
        entry=100.0,
        stop_loss=95.0,
        target_1=110.0,
    )

    first = manager.initial_entry(
        trade,
        price=100.0,
    )

    retest = manager.retest_entry(
        trade,
        price=101.0,
    )

    reentry = manager.reentry(
        trade,
        price=99.5,
    )

    assert first.entry_type == EntryType.INITIAL

    assert retest.entry_type == EntryType.RETEST

    assert reentry.entry_type == EntryType.REENTRY

    assert len(trade.entries) == 3

    assert trade.targets.stop_loss == 95.0

    assert trade.targets.target_1 == 110.0
