from __future__ import annotations

from evidence_v2 import (
    EvidencePolarity,
    EvidenceRecord,
)

from .classifier import DecisionClassifier
from .enums import (
    DecisionAction,
    DecisionDirection,
    EntryType,
)
from .explain import build_explanation
from .gates import DecisionGates
from .models import DecisionResult
from .rules import (
    DEFAULT_THRESHOLDS,
    DecisionThresholds,
)


class DecisionEngine:
    """
    Converts market hypothesis + confluence into a
    controlled decision.

    It does not open trades.
    It does not modify SL/TP.
    """

    def __init__(
        self,
        thresholds: DecisionThresholds
        = DEFAULT_THRESHOLDS,
    ) -> None:

        self.thresholds = thresholds

        self.gates = DecisionGates(
            thresholds
        )

        self.classifier = DecisionClassifier(
            thresholds
        )

    def evaluate(
        self,
        *,
        evidence: list[EvidenceRecord],
        confluence_score: float,
        hypothesis_polarity: EvidencePolarity,
        entry_type: EntryType = EntryType.INITIAL,
        metadata: dict[str, object] | None = None,
    ) -> DecisionResult:

        gate_result = self.gates.evaluate(
            evidence=evidence,
            confluence_score=confluence_score,
            hypothesis_polarity=hypothesis_polarity,
        )

        accepted = (
            len(gate_result.rejection_reasons) == 0
        )

        if not accepted:

            action = DecisionAction.REJECT

            direction = self._direction(
                hypothesis_polarity
            )

        else:

            action = DecisionAction.ACCEPT

            direction = self._direction(
                hypothesis_polarity
            )

        supporting = tuple(
            item.evidence_id
            for item in evidence
            if item.polarity
            == hypothesis_polarity
        )

        conflicting = tuple(
            item.evidence_id
            for item in evidence
            if (
                hypothesis_polarity
                != EvidencePolarity.NEUTRAL
                and
                item.polarity
                != hypothesis_polarity
            )
        )

        grade = self.classifier.classify(
            confluence_score=confluence_score,
            supporting_evidence_count=len(
                supporting
            ),
            accepted=accepted,
        )

        explanation = build_explanation(
            action=action.value,
            direction=direction.value,
            grade=grade.value,
            confidence=confluence_score,
            gates=gate_result.gates,
        )

        return DecisionResult(
            action=action,
            direction=direction,
            grade=grade,
            confidence=confluence_score,
            confluence_score=confluence_score,
            entry_type=entry_type,
            gates=gate_result.gates,
            rejection_reasons=(
                gate_result.rejection_reasons
            ),
            supporting_evidence=supporting,
            conflicting_evidence=conflicting,
            explanation=explanation,
            metadata=metadata or {},
        )

    @staticmethod
    def _direction(
        polarity: EvidencePolarity,
    ) -> DecisionDirection:

        if polarity == EvidencePolarity.BULLISH:
            return DecisionDirection.LONG

        if polarity == EvidencePolarity.BEARISH:
            return DecisionDirection.SHORT

        return DecisionDirection.NEUTRAL
