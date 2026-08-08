from shadow_outcomes import (
    OutcomeStatus,
    ShadowOutcomeTracker,
)


def test_complete_shadow_lifecycle(tmp_path):

    path = tmp_path / "shadow.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    outcome = tracker.register(
        signal_id="BTC-4H-E2E",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="FVG_SCALP_4_CONFIRMS",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
        target_3=115.0,
        target_4=120.0,
        macro_target=130.0,
    )

    assert outcome.status == OutcomeStatus.PENDING

    tracker.process_bar(
        signal_id="BTC-4H-E2E",
        high=103.0,
        low=99.0,
    )

    assert (
        tracker.outcomes[
            "BTC-4H-E2E"
        ].status
        == OutcomeStatus.PENDING
    )

    tracker.process_bar(
        signal_id="BTC-4H-E2E",
        high=111.0,
        low=106.0,
    )

    outcome = tracker.outcomes[
        "BTC-4H-E2E"
    ]

    assert outcome.status == OutcomeStatus.TARGET_2
    assert outcome.exit_price == 110.0
    assert outcome.r_multiple == 2.0

    # Persistence/recovery
    restored = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    recovered = restored.outcomes[
        "BTC-4H-E2E"
    ]

    assert recovered.status == OutcomeStatus.TARGET_2
    assert recovered.exit_price == 110.0
    assert recovered.r_multiple == 2.0


def test_expiration_is_persisted(tmp_path):

    path = tmp_path / "shadow.json"

    tracker = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    tracker.register(
        signal_id="ETH-1H-EXP",
        symbol="ETH-USDT",
        timeframe="1h",
        strategy="TEST",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
    )

    tracker.expire(
        "ETH-1H-EXP"
    )

    assert (
        tracker.outcomes[
            "ETH-1H-EXP"
        ].status
        == OutcomeStatus.EXPIRED
    )

    restored = ShadowOutcomeTracker(
        storage_path=str(path)
    )

    assert (
        restored.outcomes[
            "ETH-1H-EXP"
        ].status
        == OutcomeStatus.EXPIRED
    )
