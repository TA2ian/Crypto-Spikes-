from trade_v2 import (
    ExitReason,
    TradeManager,
    TradeStatus,
)


def test_trade_lifecycle() -> None:

    manager = TradeManager()

    trade = manager.create_trade(
        direction="long",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
    )

    assert trade.status == TradeStatus.READY

    manager.initial_entry(
        trade,
        price=100.0,
    )

    assert trade.status == TradeStatus.ACTIVE

    manager.partial_tp(trade)

    assert trade.status == TradeStatus.PARTIAL_TP

    manager.trailing(trade)

    assert trade.status == TradeStatus.TRAILING

    manager.close(
        trade,
        reason=ExitReason.TARGET_2,
    )

    assert trade.status == TradeStatus.CLOSED

    assert (
        trade.exit_reason
        == ExitReason.TARGET_2
    )
