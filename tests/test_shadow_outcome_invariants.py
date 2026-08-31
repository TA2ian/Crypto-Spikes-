import pytest

from shadow_outcomes import (
    OutcomeDirection,
    OutcomeStatus,
    ShadowOutcomeTracker,
    ShadowOutcomeValidationError,
)


def test_short_target_and_r_multiple_are_direction_aware(tmp_path):
    tracker = ShadowOutcomeTracker(
        storage_path=str(tmp_path / "outcomes.json")
    )

    outcome = tracker.register(
        signal_id="ETH-SHORT-001",
        symbol="ETH-USDT",
        timeframe="1h",
        strategy="TEST",
        entry=100.0,
        stop_loss=105.0,
        direction="short",
        target_1=95.0,
        target_2=90.0,
    )

    assert outcome.direction == OutcomeDirection.SHORT

    result = tracker.process_bar(
        signal_id="ETH-SHORT-001",
        high=101.0,
        low=94.0,
    )

    assert result is not None
    assert result.status == OutcomeStatus.TARGET_1
    assert result.exit_price == 95.0
    assert result.r_multiple == pytest.approx(1.0)


def test_short_stop_wins_on_ambiguous_candle(tmp_path):
    tracker = ShadowOutcomeTracker(
        storage_path=str(tmp_path / "outcomes.json")
    )

    tracker.register(
        signal_id="ETH-SHORT-002",
        symbol="ETH-USDT",
        timeframe="1h",
        strategy="TEST",
        entry=100.0,
        stop_loss=105.0,
        direction="sell",
        target_1=95.0,
    )

    result = tracker.process_bar(
        signal_id="ETH-SHORT-002",
        high=106.0,
        low=94.0,
    )

    assert result is not None
    assert result.status == OutcomeStatus.STOPPED
    assert result.exit_price == 105.0
    assert result.r_multiple == pytest.approx(-1.0)


def test_multiple_targets_in_one_candle_resolve_at_first_target(tmp_path):
    tracker = ShadowOutcomeTracker(
        storage_path=str(tmp_path / "outcomes.json")
    )

    tracker.register(
        signal_id="BTC-MULTI-001",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="TEST",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
        target_3=115.0,
        target_4=120.0,
    )

    result = tracker.process_bar(
        signal_id="BTC-MULTI-001",
        high=125.0,
        low=99.0,
    )

    assert result is not None
    assert result.status == OutcomeStatus.TARGET_1
    assert result.exit_price == 105.0
    assert result.r_multiple == pytest.approx(1.0)


def test_invalid_bar_is_rejected_without_mutating_observation_count(tmp_path):
    tracker = ShadowOutcomeTracker(
        storage_path=str(tmp_path / "outcomes.json")
    )

    tracker.register(
        signal_id="BTC-BAR-001",
        symbol="BTC-USDT",
        timeframe="1h",
        strategy="TEST",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
    )

    with pytest.raises(ShadowOutcomeValidationError):
        tracker.process_bar(
            signal_id="BTC-BAR-001",
            high=99.0,
            low=101.0,
        )

    assert tracker.outcomes["BTC-BAR-001"].bars_observed == 0


def test_invalid_short_levels_are_rejected(tmp_path):
    tracker = ShadowOutcomeTracker(
        storage_path=str(tmp_path / "outcomes.json")
    )

    with pytest.raises(ShadowOutcomeValidationError):
        tracker.register(
            signal_id="ETH-SHORT-INVALID",
            symbol="ETH-USDT",
            timeframe="1h",
            strategy="TEST",
            entry=100.0,
            stop_loss=95.0,
            direction="short",
            target_1=90.0,
        )


def test_legacy_persisted_outcomes_default_to_long(tmp_path):
    path = tmp_path / "legacy.json"
    path.write_text(
        """[
          {
            "signal_id": "BTC-LEGACY-001",
            "symbol": "BTC-USDT",
            "timeframe": "1h",
            "strategy": "TEST",
            "entry": 100.0,
            "stop_loss": 95.0,
            "target_1": 105.0,
            "target_2": null,
            "target_3": null,
            "target_4": null,
            "macro_target": null,
            "status": "pending",
            "entry_time": "2026-08-31T00:00:00+00:00",
            "exit_time": null,
            "exit_price": null,
            "r_multiple": null,
            "bars_observed": 0,
            "metadata": {}
          }
        ]""",
        encoding="utf-8",
    )

    tracker = ShadowOutcomeTracker(storage_path=str(path))

    assert tracker.outcomes["BTC-LEGACY-001"].direction == OutcomeDirection.LONG
