from __future__ import annotations

from dataclasses import dataclass

from .categories import (
    ConfluenceStrength,
    EvidencePolarity,
)
from .models import EvidenceRecord
from .scorer import EvidenceScorer


@dataclass(frozen=True, slots=True)
class ConfluenceResult:
    polarity: EvidencePolarity

    score: float

    bullish_score: float
    bearish_score: float

    evidence_count: int

    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]

    strength: ConfluenceStrength


class ConfluenceEngine:
    """
    Combines independent evidence into a normalized confluence result.
    """

    def __init__(
        self,
        *,
        minimum_evidence: int = 2,
    ) -> None:

        if minimum_evidence < 1:
            raise ValueError(
                "minimum_evidence must be >= 1"
            )

        self.minimum_evidence = minimum_evidence
        self.scorer = EvidenceScorer()

    def evaluate(
        self,
        evidence: list[EvidenceRecord],
    ) -> ConfluenceResult:

        if len(evidence) < self.minimum_evidence:
            return ConfluenceResult(
                polarity=EvidencePolarity.NEUTRAL,
                score=0.0,
                bullish_score=0.0,
                bearish_score=0.0,
                evidence_count=len(evidence),
                supporting_evidence=(),
                conflicting_evidence=(),
                strength=ConfluenceStrength.VERY_WEAK,
            )

        scores = self.scorer.score(evidence)

        total = (
            scores.bullish
            + scores.bearish
            + scores.neutral
        )

        if total <= 0:
            normalized_bullish = 0.0
            normalized_bearish = 0.0
        else:
            normalized_bullish = (
                scores.bullish / total
            )

            normalized_bearish = (
                scores.bearish / total
            )

        if normalized_bullish > normalized_bearish:
            polarity = EvidencePolarity.BULLISH
            score = normalized_bullish

        elif normalized_bearish > normalized_bullish:
            polarity = EvidencePolarity.BEARISH
            score = normalized_bearish

        else:
            polarity = EvidencePolarity.NEUTRAL
            score = 0.0

        supporting = tuple(
            item.evidence_id
            for item in evidence
            if item.polarity == polarity
        )

        conflicting = tuple(
            item.evidence_id
            for item in evidence
            if (
                polarity != EvidencePolarity.NEUTRAL
                and item.polarity != polarity
            )
        )

        return ConfluenceResult(
            polarity=polarity,
            score=score,
            bullish_score=normalized_bullish,
            bearish_score=normalized_bearish,
            evidence_count=len(evidence),
            supporting_evidence=supporting,
            conflicting_evidence=conflicting,
            strength=self._classify(score),
        )

    @staticmethod
    def _classify(
        score: float,
    ) -> ConfluenceStrength:

        if score < 0.20:
            return ConfluenceStrength.VERY_WEAK

        if score < 0.40:
            return ConfluenceStrength.WEAK

        if score < 0.60:
            return ConfluenceStrength.MODERATE

        if score < 0.80:
            return ConfluenceStrength.STRONG

        return ConfluenceStrength.VERY_STRONG
