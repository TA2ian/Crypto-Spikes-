from types import SimpleNamespace

from shadow_outcome_integration import (
    ShadowOutcomeIntegration,
)


class FakeTracker:
    def __init__(self):
        self.calls = []

    def register(self, **kwargs):
        self.calls.append(kwargs)

        return SimpleNamespace(
            signal_id=kwargs["signal_id"],
            status=SimpleNamespace(
                value="registered"
            ),
            symbol=kwargs["symbol"],
            timeframe=kwargs["timeframe"],
            entry=kwargs["entry"],
            stop_loss=kwargs["stop_loss"],
            target_1=kwargs["target_1"],
            target_2=kwargs["target_2"],
            target_3=kwargs["target_3"],
            target_4=kwargs["target_4"],
            macro_target=kwargs["macro_target"],
            metadata=kwargs["metadata"],
        )


def make_signal():
    return {
        "symbol": "BTC-USDT",
        "timeframe": "1h",
        "price": 100.0,
        "stop_loss": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "target3": 115.0,
        "target4": 120.0,
        "macro_target": 130.0,
    }


def test_shadow_registration_is_observation_only():
    tracker = FakeTracker()

    integration = ShadowOutcomeIntegration(
        tracker=tracker
    )

    result = SimpleNamespace(
        action="accept",
        audit_event_id="audit-isolation-001",
    )

    outcome = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    assert outcome is not None

    assert len(tracker.calls) == 1

    registered = tracker.calls[0]

    assert registered["symbol"] == "BTC-USDT"

    assert registered["entry"] == 100.0

    assert (
        registered["metadata"]["mode"]
        == "SHADOW"
    )

    # Explicitly verify that the integration
    # receives no execution/trading object.
    assert "trade_manager" not in registered
    assert "open_trade" not in registered
    assert "execute_trade" not in registered


def test_rejected_signal_has_no_side_effect():
    tracker = FakeTracker()

    integration = ShadowOutcomeIntegration(
        tracker=tracker
    )

    result = SimpleNamespace(
        action="reject",
        audit_event_id="audit-isolation-002",
    )

    outcome = (
        integration.register_if_accepted(
            signal=make_signal(),
            strategy_type="FVG_SCALP_4_CONFIRMS",
            result=result,
        )
    )

    assert outcome is None

    assert tracker.calls == []
