from shadow_outcomes import ShadowOutcomeTracker


def test_shadow_outcomes_survive_tracker_reload(tmp_path):
    storage = tmp_path / "shadow_outcomes.json"

    first = ShadowOutcomeTracker(storage_path=str(storage))
    outcome = first.register(
        signal_id="BTC-USDT-4h-FVG-100",
        symbol="BTC-USDT",
        timeframe="4h",
        strategy="FVG_SCALP_4_CONFIRMS",
        entry=100.0,
        stop_loss=95.0,
        target_1=105.0,
        target_2=110.0,
        metadata={
            "candle_timestamp": "1000",
            "audit_event_id": "audit-persist",
        },
    )

    outcome.metadata["last_processed_timestamp"] = "2000"
    first.save()

    second = ShadowOutcomeTracker(storage_path=str(storage))
    restored = second.outcomes[outcome.signal_id]

    assert restored.signal_id == outcome.signal_id
    assert restored.entry == 100.0
    assert restored.stop_loss == 95.0
    assert restored.target_1 == 105.0
    assert restored.metadata["candle_timestamp"] == "1000"
    assert restored.metadata["last_processed_timestamp"] == "2000"
    assert restored.metadata["audit_event_id"] == "audit-persist"
