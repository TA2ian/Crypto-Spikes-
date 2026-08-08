from risk_v2 import (
    EligibilityStatus,
    RiskEligibilityEngine,
    RiskParameters,
    StrategyType,
)


def make_risk() -> RiskParameters:

    return RiskParameters(
        entry_price=100.0,
        stop_loss=95.0,
        target_1=110.0,
        account_equity=10_000.0,
        risk_percent=1.0,
        atr=2.0,
    )


def test_eligible_setup() -> None:

    result = RiskEligibilityEngine().evaluate(
        risk=make_risk(),
        active_positions=1,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=2.0,
        halal_eligible=True,
        asset_supported=True,
        evidence_names=[
            "fvg",
        ],
        confluence_score=0.80,
        strategies=[
            StrategyType.FVG_SCALP,
        ],
    )

    assert (
        result.status
        == EligibilityStatus.ELIGIBLE
    )

    assert result.eligible is True

    assert (
        StrategyType.FVG_SCALP
        in result.eligible_strategies
    )


def test_blocks_non_halal_asset() -> None:

    result = RiskEligibilityEngine().evaluate(
        risk=make_risk(),
        active_positions=1,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=2.0,
        halal_eligible=False,
        asset_supported=True,
        evidence_names=[
            "fvg",
        ],
        confluence_score=0.80,
        strategies=[
            StrategyType.FVG_SCALP,
        ],
    )

    assert (
        result.status
        == EligibilityStatus.BLOCKED
    )

    assert result.eligible is False


def test_blocks_bad_rr() -> None:

    result = RiskEligibilityEngine().evaluate(
        risk=make_risk(),
        active_positions=1,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=1.0,
        halal_eligible=True,
        asset_supported=True,
        evidence_names=[
            "fvg",
        ],
        confluence_score=0.80,
        strategies=[
            StrategyType.FVG_SCALP,
        ],
    )

    assert result.eligible is False


def test_blocks_excessive_active_positions() -> None:

    result = RiskEligibilityEngine().evaluate(
        risk=make_risk(),
        active_positions=5,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=2.0,
        halal_eligible=True,
        asset_supported=True,
        evidence_names=[
            "fvg",
        ],
        confluence_score=0.80,
        strategies=[
            StrategyType.FVG_SCALP,
        ],
    )

    assert result.eligible is False
