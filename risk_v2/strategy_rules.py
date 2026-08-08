from __future__ import annotations

from collections.abc import Iterable

from .enums import StrategyType
from .models import StrategyEligibility


def evaluate_strategy(
    *,
    strategy: StrategyType,
    evidence_names: Iterable[str],
    confluence_score: float,
    htf_bullish: bool,
    macro_bullish: bool,
    risk_reward_value: float,
    minimum_rr: float,
) -> StrategyEligibility:

    evidence = {
        item.lower()
        for item in evidence_names
    }

    reasons: list[str] = []

    score = confluence_score

    if strategy == StrategyType.WYCKOFF_SMC:

        required = {
            "wyckoff",
            "smc",
        }

        matched = sum(
            item in evidence
            for item in required
        )

        score += matched * 0.05

        if matched < 1:
            reasons.append(
                "Wyckoff or SMC evidence missing."
            )

    elif strategy == StrategyType.CVD_SQUEEZE:

        if "cvd" not in evidence:
            reasons.append(
                "CVD evidence missing."
            )

        if "bb_squeeze" not in evidence:
            reasons.append(
                "BB squeeze evidence missing."
            )

    elif strategy == StrategyType.TREND_FOLLOWING:

        if not htf_bullish:
            reasons.append(
                "Higher timeframe trend is not bullish."
            )

        if not macro_bullish:
            reasons.append(
                "Macro trend is not bullish."
            )

    elif strategy == StrategyType.MEAN_REVERSION:

        if "mean_reversion" not in evidence:
            reasons.append(
                "Mean reversion evidence missing."
            )

    elif strategy == StrategyType.CHART_PATTERN:

        if "chart_pattern" not in evidence:
            reasons.append(
                "Verified chart pattern missing."
            )

    elif strategy == StrategyType.FVG_SCALP:

        if "fvg" not in evidence:
            reasons.append(
                "FVG evidence missing."
            )

    elif strategy == StrategyType.ULTIMATE_A_PLUS:

        if confluence_score < 0.82:
            reasons.append(
                "A+ confluence threshold not met."
            )

        if not htf_bullish:
            reasons.append(
                "A+ requires bullish HTF alignment."
            )

        if not macro_bullish:
            reasons.append(
                "A+ requires bullish macro alignment."
            )

    elif strategy == StrategyType.CAPITULATION:

        if "capitulation" not in evidence:
            reasons.append(
                "Capitulation evidence missing."
            )

    if risk_reward_value < minimum_rr:
        reasons.append(
            "Risk/reward is below minimum."
        )

    eligible = not reasons

    return StrategyEligibility(
        strategy=strategy,
        eligible=eligible,
        score=min(score, 1.0),
        reasons=tuple(reasons),
    )
