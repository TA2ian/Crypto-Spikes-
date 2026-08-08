from __future__ import annotations

from dataclasses import dataclass

from .categories import EvidencePolarity
from .models import EvidenceRecord


@dataclass(frozen=True, slots=True)
class PolarityScore:
    bullish: float
    bearish: float
    neutral: float


class EvidenceScorer:
    """
    Calculates normalized aggregate evidence scores.

    It does not produce BUY/SELL decisions.
    """

    def score(
        self,
        evidence: list[EvidenceRecord],
    ) -> PolarityScore:

        bullish = 0.0
        bearish = 0.0
        neutral = 0.0

        for item in evidence:
            value = item.effective_score

            if item.polarity == EvidencePolarity.BULLISH:
                bullish += value

            elif item.polarity == EvidencePolarity.BEARISH:
                bearish += value

            else:
                neutral += value

        return PolarityScore(
            bullish=bullish,
            bearish=bearish,
            neutral=neutral,
        )
