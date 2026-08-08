from __future__ import annotations

from dataclasses import dataclass

from .categories import (
    ConfluenceStrength,
    EvidencePolarity,
)
from .confluence import ConfluenceResult


@dataclass(frozen=True, slots=True)
class MarketHypothesis:
    """
    A market hypothesis generated from confluence.

    A hypothesis is not yet an executable trading decision.
    """

    polarity: EvidencePolarity

    confidence: float

    strength: ConfluenceStrength

    thesis: str

    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]


class HypothesisEngine:
    """
    Converts confluence into an explainable market hypothesis.
    """

    def build(
        self,
        result: ConfluenceResult,
    ) -> MarketHypothesis:

        if result.polarity == EvidencePolarity.BULLISH:

            thesis = (
                "Bullish market hypothesis supported by "
                f"{result.evidence_count} evidence items."
            )

        elif result.polarity == EvidencePolarity.BEARISH:

            thesis = (
                "Bearish market hypothesis supported by "
                f"{result.evidence_count} evidence items."
            )

        else:

            thesis = (
                "No directional market hypothesis has "
                "sufficient confluence."
            )

        return MarketHypothesis(
            polarity=result.polarity,
            confidence=result.score,
            strength=result.strength,
            thesis=thesis,
            supporting_evidence=result.supporting_evidence,
            conflicting_evidence=result.conflicting_evidence,
        )
