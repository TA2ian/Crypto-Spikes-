from types import SimpleNamespace

import shadow_outcome_integration as soi
from shadow_outcome_integration import ShadowOutcomeIntegration


def test_okx_history_paginates_until_oldest_pending_signal(monkeypatch, tmp_path):
    integration = ShadowOutcomeIntegration()
    integration.tracker.storage_path = str(tmp_path / "outcomes.json")

    signal = {
        "symbol": "BTC-USDT",
        "timeframe": "15m",
        "price": 100.0,
        "stop_loss": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "target3": 115.0,
        "target4": 120.0,
        "candle_timestamp": "1000",
    }
    integration.register_if_accepted(
        signal=signal,
        strategy_type="FVG_SCALP_4_CONFIRMS",
        result=SimpleNamespace(action="accept", audit_event_id="audit-history-pages"),
    )

    calls = []

    page_1 = [
        ["3000", "100", "104", "99", "103", "0", "0", "0", "1"],
        ["2000", "100", "106", "104", "105", "0", "0", "0", "1"],
    ]
    page_2 = [
        ["1500", "100", "103", "99", "102", "0", "0", "0", "1"],
        ["1000", "100", "120", "100", "110", "0", "0", "0", "1"],
    ]

    def fake_get(url, params, timeout):
        calls.append(dict(params))
        rows = page_1 if len(calls) == 1 else page_2
        return SimpleNamespace(
            raise_for_status=lambda: None,
            json=lambda: {"code": "0", "data": rows},
        )

    monkeypatch.setattr(soi.requests, "get", fake_get)

    processed = integration.process_market_bar(
        symbol="BTC-USDT",
        timeframe="15m",
        high=0,
        low=0,
        timestamp="3000",
    )

    assert len(calls) == 2
    assert calls[1]["after"] == "2000"
    assert len(processed) == 0
    assert integration.tracker.outcomes[next(iter(integration.tracker.outcomes))].resolved is False

    # The signal candle itself must never resolve the outcome. The next
    # completed candle at 1500 is also after 1000 and remains below TP1.
    outcome = next(iter(integration.tracker.outcomes.values()))
    assert outcome.metadata["last_processed_timestamp"] == "3000"
