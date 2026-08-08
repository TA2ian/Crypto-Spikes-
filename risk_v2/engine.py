from __future__ import annotations

from collections.abc import Iterable

from .eligibility import EligibilityGates
from .enums import (
    EligibilityStatus,
    RiskLevel,
    StrategyType,
)
from .models import (
    EligibilityResult,
    RiskParameters,
)
from .strategy_rules import evaluate_strategy
from .thresholds import (
    DEFAULT_RISK_THRESHOLDS,
    RiskThresholds,
)


class RiskEligibilityEngine:

    def __init__(
        self,
        thresholds: RiskThresholds
        = DEFAULT_RISK_THRESHOLDS,
    ) -> None:

        self.thresholds = thresholds

        self.gates = EligibilityGates(
            thresholds
        )

    def evaluate(
        self,
        *,
        risk: RiskParameters,
        active_positions: int,
        htf_bullish: bool,
        macro_bullish: bool,
        risk_reward_value: float,
        halal_eligible: bool,
        asset_supported: bool,
        evidence_names: Iterable[str],
        confluence_score: float,
        strategies: Iterable[StrategyType],
        decision_id: str | None = None,
    ) -> EligibilityResult:

        evidence = list(evidence_names)

        checks, blocked = self.gates.evaluate(
            risk=risk,
            active_positions=active_positions,
            htf_bullish=htf_bullish,
            macro_bullish=macro_bullish,
            risk_reward_value=risk_reward_value,
            halal_eligible=halal_eligible,
            asset_supported=asset_supported,
        )

        strategy_results = tuple(
            evaluate_strategy(
                strategy=strategy,
                evidence_names=evidence,
                confluence_score=confluence_score,
                htf_bullish=htf_bullish,
                macro_bullish=macro_bullish,
                risk_reward_value=risk_reward_value,
                minimum_rr=(
                    self.thresholds.minimum_rr
                ),
            )
            for strategy in strategies
        )

        eligible_strategies = tuple(
            result.strategy
            for result in strategy_results
            if result.eligible
        )

        if blocked:
            status = EligibilityStatus.BLOCKED

        elif eligible_strategies:
            status = EligibilityStatus.ELIGIBLE

        else:
            status = EligibilityStatus.BLOCKED

        risk_score = self._risk_score(
            checks
        )

        risk_level = self._risk_level(
            risk_score
        )

        explanation = self._explain(
            status=status,
            blocked=blocked,
            eligible_strategies=eligible_strategies,
            risk_level=risk_level,
        )

        return EligibilityResult(
            status=status,
            risk_level=risk_level,
            risk_score=risk_score,
            checks=checks,
            blocked_reasons=blocked,
            eligible_strategies=eligible_strategies,
            strategy_results=strategy_results,
            decision_id=decision_id,
            explanation=explanation,
        )

    @staticmethod
    def _risk_score(
        checks,
    ) -> float:

        if not checks:
            return 1.0

        failures = sum(
            not check.passed
            for check in checks
        )

        return min(
            1.0,
            failures / len(checks),
        )

    @staticmethod
    def _risk_level(
        score: float,
    ) -> RiskLevel:

        if score < 0.20:
            return RiskLevel.LOW

        if score < 0.40:
            return RiskLevel.MODERATE

        if score < 0.70:
            return RiskLevel.HIGH

        return RiskLevel.EXTREME

    @staticmethod
    def _explain(
        *,
        status: EligibilityStatus,
        blocked,
        eligible_strategies,
        risk_level: RiskLevel,
    ) -> str:

        if status == EligibilityStatus.ELIGIBLE:

            strategies = ", ".join(
                strategy.value
                for strategy in eligible_strategies
            )

            return (
                "Setup is eligible. "
                f"Risk level={risk_level.value}. "
                f"Eligible strategies={strategies}."
            )

        reasons = ", ".join(
            reason.value
            for reason in blocked
        )

        return (
            "Setup is blocked. "
            f"Risk level={risk_level.value}. "
            f"Reasons={reasons or 'strategy eligibility failed'}."
        )
