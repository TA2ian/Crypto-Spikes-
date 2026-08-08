from __future__ import annotations

from .enums import DecisionGrade
from .rules import DecisionThresholds


class DecisionClassifier:

    def __init__(
        self,
        thresholds: DecisionThresholds,
    ) -> None:
        self.thresholds = thresholds

    def classify(
        self,
        *,
        confluence_score: float,
        supporting_evidence_count: int,
        accepted: bool,
    ) -> DecisionGrade:

        if not accepted:
            return DecisionGrade.INVALID

        if (
            confluence_score
            >= self.thresholds.a_plus_confluence
            and
            supporting_evidence_count
            >= self.thresholds.a_plus_min_supporting_evidence
        ):
            return DecisionGrade.A_PLUS

        if (
            confluence_score
            >= self.thresholds.strong_confluence
        ):
            return DecisionGrade.A

        if (
            confluence_score
            >= self.thresholds.minimum_confluence
        ):
            return DecisionGrade.B

        return DecisionGrade.C
