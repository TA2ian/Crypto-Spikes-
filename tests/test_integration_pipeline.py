from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
)

from integration_v2 import (
    ExecutionMode,
    V2Pipeline,
)

from risk_v2 import (
    RiskParameters,
    StrategyType,
)


def ev(
    name: str,
) -> EvidenceRecord:

    return EvidenceRecord(
        category=EvidenceCategory.STRUCTURE,
        polarity=EvidencePolarity.BULLISH,
        name=name,
        strength=1.0,
        reliability=1.0,
        freshness=1.0,
        timeframe="4h",
        source="test",
    )


def kwargs():

    return dict(
        symbol="BTCUSDT",

        evidence=[
            ev("fvg"),
            ev("structure"),
            ev("trend"),
        ],

        confluence_score=0.75,

        hypothesis_polarity=(
            EvidencePolarity.BULLISH
        ),

        risk=RiskParameters(
            entry_price=100,
            stop_loss=95,
            account_equity=10000,
            risk_percent=1,
            atr=2,
        ),

        active_positions=0,

        htf_bullish=True,

        macro_bullish=True,

        risk_reward_value=2.0,

        halal_eligible=True,

        asset_supported=True,

        strategies=[
            StrategyType.FVG_SCALP
        ],

        entry=100,

        stop_loss=95,

        targets=(
            110,
            None,
            None,
            None,
        ),
    )


def test_shadow_mode_never_creates_trade():

    result = V2Pipeline(
        mode=ExecutionMode.SHADOW
    ).evaluate(
        **kwargs()
    )

    assert result.decision.accepted

    assert result.eligibility.eligible

    assert result.trade is None

    assert (
        result.audit_event_id
        is not None
    )

    assert (
        len(result.audit_event_id)
        > 0
    )


def test_live_mode_creates_trade_only_after_both_gates_pass():

    result = V2Pipeline(
        mode=ExecutionMode.LIVE
    ).evaluate(
        **kwargs()
    )

    assert result.trade is not None

    assert (
        result.trade.targets.target_1
        == 110
    )


def test_blocked_setup_cannot_create_trade_in_live_mode():

    data = kwargs()

    data[
        "halal_eligible"
    ] = False

    result = V2Pipeline(
        mode=ExecutionMode.LIVE
    ).evaluate(
        **data
    )

    assert result.trade is None
