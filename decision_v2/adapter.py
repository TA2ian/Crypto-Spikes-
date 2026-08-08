from __future__ import annotations

from models.decision import Decision, DecisionAction, RiskLevel

from .enums import (
    DecisionAction as V2DecisionAction,
    DecisionDirection,
)
from .models import DecisionResult


def to_domain_decision(
    result: DecisionResult,
) -> Decision:
    """
    Convert a V2 evaluation result into the canonical domain Decision.

    The adapter keeps the V2 decision vocabulary
    (ACCEPT/REJECT/WAIT) separate from the canonical
    domain action vocabulary (BUY/SELL/etc.).

    It does not create or modify a TradeCase.
    """

    if result.action == V2DecisionAction.ACCEPT:

        if result.direction == DecisionDirection.LONG:
            action = DecisionAction.BUY

        elif result.direction == DecisionDirection.SHORT:
            action = DecisionAction.SELL

        else:
            action = DecisionAction.WATCH

    elif result.action == V2DecisionAction.WAIT:

        action = DecisionAction.WATCH

    else:

        action = DecisionAction.NO_ACTION

    if (
        result.grade.value == "A+"
        and result.confidence >= 0.82
    ):
        risk_level = RiskLevel.MODERATE

    elif result.confidence >= 0.70:

        risk_level = RiskLevel.MODERATE

    elif result.confidence >= 0.55:

        risk_level = RiskLevel.HIGH

    else:

        risk_level = RiskLevel.UNKNOWN

    return Decision(
        action=action,
        confidence=result.confidence,
        risk_level=risk_level,
        evidence_ids=list(
            dict.fromkeys(
                [
                    *result.supporting_evidence,
                    *result.conflicting_evidence,
                ]
            )
        ),
        supporting_evidence=list(
            result.supporting_evidence
        ),
        conflicting_evidence=list(
            result.conflicting_evidence
        ),
        reasoning=result.explanation,
        decision_id=result.decision_id,
        metadata={
            "v2_grade": result.grade.value,
            "v2_entry_type": result.entry_type.value,
            **result.metadata,
        },
    )
