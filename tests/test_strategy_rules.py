from risk_v2 import (
    StrategyType,
)
from risk_v2.strategy_rules import (
    evaluate_strategy,
)


def test_fvg_strategy_requires_fvg() -> None:

    result = evaluate_strategy(
        strategy=StrategyType.FVG_SCALP,
        evidence_names=[
            "rsi",
            "volume",
        ],
        confluence_score=0.80,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=2.0,
        minimum_rr=1.5,
    )

    assert result.eligible is False


def test_fvg_strategy_passes_with_fvg() -> None:

    result = evaluate_strategy(
        strategy=StrategyType.FVG_SCALP,
        evidence_names=[
            "fvg",
        ],
        confluence_score=0.80,
        htf_bullish=True,
        macro_bullish=True,
        risk_reward_value=2.0,
        minimum_rr=1.5,
    )

    assert result.eligible is True
