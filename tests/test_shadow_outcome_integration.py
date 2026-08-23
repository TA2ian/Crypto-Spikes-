from types import SimpleNamespace

from shadow_outcome_integration import ShadowOutcomeIntegration


def make_signal():
    return {
        "symbol": "BTC-USDT",
        "timeframe": "4h",
        "price": 100.0,
        "stop_loss": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "target3": 115.0,
        "target4": 120.0,
        "macro_target": 130.0,
    }


def make_integration(tmp_path):
    integration = ShadowOutcomeIntegration()
    integration.tracker.storage_path = str(tmp_path / "outcomes.json")
    return integration


def test_accepted_shadow_signal_is_registered(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-001")

    outcome = integration.register_if_accepted(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    assert outcome is not None
    assert outcome.symbol == "BTC-USDT"
    assert outcome.timeframe == "4h"
    assert outcome.entry == 100.0
    assert outcome.stop_loss == 95.0
    assert outcome.target_1 == 105.0
    assert outcome.metadata["mode"] == "SHADOW"
    assert outcome.metadata["audit_event_id"] == "audit-001"


def test_rejected_shadow_signal_is_not_registered(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="reject", audit_event_id="audit-002")

    outcome = integration.register_if_accepted(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    assert outcome is None
    assert integration.tracker.outcomes == {}


def test_missing_shadow_result_is_not_registered(tmp_path):
    integration = make_integration(tmp_path)

    outcome = integration.register_if_accepted(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=None,
    )

    assert outcome is None
    assert integration.tracker.outcomes == {}


def test_duplicate_signal_does_not_create_duplicate_outcome(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-003")

    first = integration.register_if_accepted(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )
    second = integration.register_if_accepted(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    assert first is second
    assert len(integration.tracker.outcomes) == 1


def test_signal_candle_is_not_processed_as_outcome(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-same-candle")
    signal = make_signal()
    signal["candle_timestamp"] = "1000"

    outcome = integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    processed = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[{"timestamp": "1000", "high": 120.0, "low": 100.0}],
    )

    assert outcome is not None
    assert processed == []
    assert outcome.resolved is False


def test_older_candle_is_not_processed_as_outcome(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-older-candle")
    signal = make_signal()
    signal["candle_timestamp"] = "2000"

    outcome = integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    processed = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[
            {"timestamp": "1000", "high": 130.0, "low": 90.0},
            {"timestamp": "2000", "high": 130.0, "low": 90.0},
        ],
    )

    assert outcome is not None
    assert processed == []
    assert outcome.resolved is False


def test_historical_completed_candle_can_resolve_shadow_outcome(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-history")
    signal = make_signal()
    signal["candle_timestamp"] = "1000"

    outcome = integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    processed = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[
            {"timestamp": "1000", "high": 120.0, "low": 100.0},
            {"timestamp": "2000", "high": 106.0, "low": 104.0},
        ],
    )

    assert outcome is not None
    assert len(processed) == 1
    assert outcome.resolved is True


def test_processed_candle_is_not_processed_twice(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-dedup")
    signal = make_signal()
    signal["candle_timestamp"] = "1000"

    outcome = integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    first = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[{"timestamp": "2000", "high": 101.0, "low": 99.0}],
    )
    second = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[{"timestamp": "2000", "high": 106.0, "low": 104.0}],
    )

    assert outcome is not None
    assert outcome.resolved is False
    assert first == []
    assert second == []
    assert outcome.metadata["last_processed_timestamp"] == "2000"


def test_next_candle_can_resolve_shadow_outcome(tmp_path):
    integration = make_integration(tmp_path)
    result = SimpleNamespace(action="accept", audit_event_id="audit-next-candle")
    signal = make_signal()
    signal["candle_timestamp"] = "1000"

    outcome = integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    processed = integration.process_market_bars(
        symbol="BTC-USDT",
        timeframe="4h",
        bars=[{"timestamp": "2000", "high": 106.0, "low": 104.0}],
    )

    assert outcome is not None
    assert len(processed) == 1
    assert outcome.resolved is True
