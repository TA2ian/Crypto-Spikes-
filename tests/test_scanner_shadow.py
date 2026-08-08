from evidence_v2 import EvidenceCategory, EvidencePolarity, EvidenceRecord
from risk_v2 import StrategyType
from scanner_shadow import (
    ScannerShadowBridge,
    compare_legacy_and_v2,
)


def make_signal():
    return {
        "symbol": "BTC-USDT",
        "timeframe": "4h",
        "type": "ارتداد من دعم",
        "price": 100.0,
        "stop_loss": 95.0,
        "target1": 105.0,
        "target2": 110.0,
        "target3": 115.0,
        "target4": 120.0,
        "stars": "⭐⭐⭐⭐",
        "confluence": [
            "وجود FVG (1.0%)",
            "كسر هيكل صعودي (BOS)",
            "تداول فوق EMA 50 & 200",
        ],
        "signal_status": "🟢 دخول أول",
    }


def test_shadow_bridge_never_creates_trade():
    bridge = ScannerShadowBridge(
        watchlist=["BTC-USDT"]
    )

    result = bridge.evaluate(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        macro_info={"macro_bullish": True},
        active_positions=0,
        account_equity=1000.0,
        risk_percent=1.0,
    )

    assert result is not None
    assert result.trade is None
    assert result.mode.value == "shadow"
    assert result.audit_event_id is not None


def test_shadow_bridge_rejects_unmapped_strategy():
    bridge = ScannerShadowBridge(
        watchlist=["BTC-USDT"]
    )

    result = bridge.evaluate(
        signal=make_signal(),
        strategy_type="STANDARD",
        macro_info={"macro_bullish": True},
        active_positions=0,
        account_equity=1000.0,
        risk_percent=1.0,
    )

    assert result is None


def test_compare_records_v2_result():
    bridge = ScannerShadowBridge(
        watchlist=["BTC-USDT"]
    )

    result = bridge.evaluate(
        signal=make_signal(),
        strategy_type="FVG_SCALP_4_CONFIRMS",
        macro_info={"macro_bullish": True},
        active_positions=0,
        account_equity=1000.0,
        risk_percent=1.0,
    )

    comparison = compare_legacy_and_v2(
        legacy_strategy="FVG_SCALP_4_CONFIRMS",
        result=result,
    )

    assert comparison["legacy_strategy"] == "FVG_SCALP_4_CONFIRMS"
    assert comparison["audit_event_id"]
    assert comparison["v2_action"] in {"accept", "reject", "wait"}
