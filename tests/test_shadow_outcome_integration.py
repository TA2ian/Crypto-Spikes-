from types import SimpleNamespace

from shadow_outcome_integration import (
    ShadowOutcomeIntegration,
)


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


def test_accepted_shadow_signal_is_registered(
    tmp_path,
):

    integration = ShadowOutcomeIntegration()

    integration.tracker.storage_path = str(
        tmp_path / "outcomes.json"
    )

    result = SimpleNamespace(
        action="accept",
        audit_event_id="audit-001",
    )

    outcome = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    assert outcome is not None

    assert outcome.symbol == "BTC-USDT"

    assert outcome.timeframe == "4h"

    assert outcome.entry == 100.0

    assert outcome.stop_loss == 95.0

    assert outcome.target_1 == 105.0

    assert (
        outcome.metadata[
            "mode"
        ]
        == "SHADOW"
    )

    assert (
        outcome.metadata[
            "audit_event_id"
        ]
        == "audit-001"
    )


def test_rejected_shadow_signal_is_not_registered(
    tmp_path,
):

    integration = ShadowOutcomeIntegration()

    integration.tracker.storage_path = str(
        tmp_path / "outcomes.json"
    )

    result = SimpleNamespace(
        action="reject",
        audit_event_id="audit-002",
    )

    outcome = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    assert outcome is None

    assert (
        integration.tracker.outcomes
        == {}
    )


def test_missing_shadow_result_is_not_registered(
    tmp_path,
):

    integration = ShadowOutcomeIntegration()

    integration.tracker.storage_path = str(
        tmp_path / "outcomes.json"
    )

    outcome = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=None,
        )
    )

    assert outcome is None

    assert (
        integration.tracker.outcomes
        == {}
    )


def test_duplicate_signal_does_not_create_duplicate_outcome(
    tmp_path,
):

    integration = ShadowOutcomeIntegration()

    integration.tracker.storage_path = str(
        tmp_path / "outcomes.json"
    )

    result = SimpleNamespace(
        action="accept",
        audit_event_id="audit-003",
    )

    first = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    second = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    assert first is second

    assert len(
        integration.tracker.outcomes
    ) == 1
