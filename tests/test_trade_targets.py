from trade_v2 import TradeManager


def test_targets_are_locked_after_creation() -> None:

    manager = TradeManager()

    trade = manager.create_trade(
        direction="long",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
        target_3=115.0,
    )

    original = trade.targets

    assert original.entry == 100.0
    assert original.stop_loss == 95.0
    assert original.target_1 == 105.0
    assert original.target_2 == 110.0
    assert original.target_3 == 115.0

    manager.initial_entry(
        trade,
        price=101.0,
    )

    assert trade.targets == original
    assert trade.targets_locked is True
