from shadow_outcomes import (
    OutcomeStatus,
    ShadowOutcomeTracker,
)


def test_register_creates_pending_outcome(
    tmp_path,
):

    path = tmp_path / "outcomes.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    outcome = tracker.register(
        signal_id="BTC-4H-001",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="FVG_SCALP_4_CONFIRMS",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
    )

    assert outcome.status == (
        OutcomeStatus.PENDING
    )

    assert outcome.entry == 100.0
    assert outcome.stop_loss == 95.0


def test_target_hit_resolves_outcome(
    tmp_path,
):

    path = tmp_path / "outcomes.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    tracker.register(
        signal_id="BTC-4H-002",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="FVG_SCALP_4_CONFIRMS",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
    )

    result = tracker.process_bar(
        signal_id="BTC-4H-002",
        high=106.0,
        low=99.0,
    )

    assert result is not None

    assert result.status == (
        OutcomeStatus.TARGET_1
    )

    assert result.exit_price == 105.0

    assert result.r_multiple == 1.0


def test_stop_loss_wins_on_ambiguous_candle(
    tmp_path,
):

    path = tmp_path / "outcomes.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    tracker.register(
        signal_id="BTC-4H-003",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="FVG_SCALP_4_CONFIRMS",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
    )

    result = tracker.process_bar(
        signal_id="BTC-4H-003",
        high=106.0,
        low=94.0,
    )

    assert result.status == (
        OutcomeStatus.STOPPED
    )

    assert result.exit_price == 95.0

    assert result.r_multiple == -1.0


def test_summary_calculates_win_rate_and_average_r(
    tmp_path,
):

    path = tmp_path / "outcomes.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    tracker.register(
        signal_id="WIN",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="TEST",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
    )

    tracker.register(
        signal_id="LOSS",
        symbol="ETH-USDT",
        timeframe="1h",
        strategy="TEST",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
    )

    tracker.process_bar(
        signal_id="WIN",
        high=106.0,
        low=99.0,
    )

    tracker.process_bar(
        signal_id="LOSS",
        high=101.0,
        low=94.0,
    )

    summary = tracker.summary()

    assert summary["total"] == 2
    assert summary["resolved"] == 2
    assert summary["wins"] == 1
    assert summary["losses"] == 1
    assert summary["win_rate"] == 0.5
    assert summary["average_r"] == 0.0
