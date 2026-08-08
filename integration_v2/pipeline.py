from __future__ import annotations

from collections.abc import Iterable, Sequence
from typing import Any

from decision_v2 import DecisionEngine
from risk_v2 import (
    RiskEligibilityEngine,
    RiskParameters,
    StrategyType,
)
from trade_v2 import (
    TradeManager,
    create_trade_from_analysis,
)

from .audit import AuditTrail
from .enums import ExecutionMode
from .models import (
    AuditEvent,
    IntegrationResult,
)


class V2Pipeline:
    """
    Orchestrates the V2 analysis stack without replacing
    or modifying the legacy scanner.
    """

    def __init__(
        self,
        *,
        decision_engine: DecisionEngine | None = None,
        risk_engine: RiskEligibilityEngine | None = None,
        trade_manager: TradeManager | None = None,
        audit: AuditTrail | None = None,
        mode: ExecutionMode = ExecutionMode.SHADOW,
    ) -> None:

        self.decision_engine = (
            decision_engine
            or DecisionEngine()
        )

        self.risk_engine = (
            risk_engine
            or RiskEligibilityEngine()
        )

        self.trade_manager = (
            trade_manager
            or TradeManager()
        )

        self.audit = (
            audit
            or AuditTrail()
        )

        self.mode = mode

    def evaluate(
        self,
        *,
        symbol: str,
        evidence: Sequence[Any],
        confluence_score: float,
        hypothesis_polarity: Any,
        risk: RiskParameters,
        active_positions: int,
        htf_bullish: bool,
        macro_bullish: bool,
        risk_reward_value: float,
        halal_eligible: bool,
        asset_supported: bool,
        strategies: Iterable[StrategyType],
        entry: float,
        stop_loss: float,
        targets: tuple[
            float | None,
            float | None,
            float | None,
            float | None,
        ] = (
            None,
            None,
            None,
            None,
        ),
        metadata: dict[str, Any] | None = None,
    ) -> IntegrationResult:

        evidence_names = [
            item.name
            for item in evidence
        ]

        # ---------------------------------------------
        # Decision
        # ---------------------------------------------

        decision = self.decision_engine.evaluate(
            evidence=list(evidence),
            confluence_score=confluence_score,
            hypothesis_polarity=hypothesis_polarity,
            metadata=metadata or {},
        )

        # ---------------------------------------------
        # Risk / Strategy Eligibility
        # ---------------------------------------------

        eligibility = self.risk_engine.evaluate(
            risk=risk,
            active_positions=active_positions,
            htf_bullish=htf_bullish,
            macro_bullish=macro_bullish,
            risk_reward_value=risk_reward_value,
            halal_eligible=halal_eligible,
            asset_supported=asset_supported,
            evidence_names=evidence_names,
            confluence_score=confluence_score,
            strategies=strategies,
            decision_id=decision.decision_id,
        )

        # ---------------------------------------------
        # Trade creation
        # ---------------------------------------------

        trade = None

        if (
            self.mode == ExecutionMode.LIVE
            and decision.accepted
            and eligibility.eligible
        ):

            trade = create_trade_from_analysis(
                decision=decision,
                eligibility=eligibility,
                manager=self.trade_manager,
                entry=entry,
                stop_loss=stop_loss,
                target_1=targets[0],
                target_2=targets[1],
                target_3=targets[2],
                target_4=targets[3],
            )

        # ---------------------------------------------
        # Audit
        # ---------------------------------------------

        event = self.audit.record(
            AuditEvent(
                event_type="v2_evaluation",
                symbol=symbol,
                mode=self.mode,
                payload={
                    "decision_id": decision.decision_id,
                    "decision_action": (
                        decision.action.value
                    ),
                    "decision_grade": (
                        decision.grade.value
                    ),
                    "confidence": (
                        decision.confidence
                    ),
                    "eligibility_status": (
                        eligibility.status.value
                    ),
                    "eligible_strategies": [
                        strategy.value
                        for strategy
                        in eligibility.eligible_strategies
                    ],
                    "blocked_reasons": [
                        reason.value
                        for reason
                        in eligibility.blocked_reasons
                    ],
                    "trade_created": (
                        trade is not None
                    ),
                },
            )
        )

        return IntegrationResult(
            mode=self.mode,
            decision=decision,
            eligibility=eligibility,
            trade=trade,
            audit_event_id=event.event_id,
        )
