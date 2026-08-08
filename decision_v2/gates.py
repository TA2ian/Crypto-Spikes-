from __future__ import annotations

from dataclasses import dataclass

from evidence_v2 import (
    EvidencePolarity,
    EvidenceRecord,
)

from .enums import (
    GateStatus,
    RejectionReason,
)
from .models import DecisionGate
from .rules import DecisionThresholds


@dataclass(frozen=True, slots=True)
class GateEvaluation:
    gates: tuple[DecisionGate, ...]
    rejection_reasons: tuple[RejectionReason, ...]


class DecisionGates:
    """
    Risk and quality gates.

    Gates do not execute trades.
    """

    def __init__(
        self,
        thresholds: DecisionThresholds,
    ) -> None:
        self.thresholds = thresholds

    def evaluate(
        self,
        evidence: list[EvidenceRecord],
        confluence_score: float,
        hypothesis_polarity: EvidencePolarity,
    ) -> GateEvaluation:

        gates: list[DecisionGate] = []
        rejections: list[RejectionReason] = []

        # -------------------------------------------------
        # Evidence count
        # -------------------------------------------------

        if len(evidence) >= self.thresholds.minimum_evidence:

            gates.append(
                DecisionGate(
                    name="minimum_evidence",
                    status=GateStatus.PASS,
                    reason=(
                        f"{len(evidence)} evidence items available."
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="minimum_evidence",
                    status=GateStatus.FAIL,
                    reason=(
                        f"Only {len(evidence)} evidence items available."
                    ),
                )
            )

            rejections.append(
                RejectionReason.INSUFFICIENT_EVIDENCE
            )

        # -------------------------------------------------
        # Confluence
        # -------------------------------------------------

        if (
            confluence_score
            >= self.thresholds.minimum_confluence
        ):

            gates.append(
                DecisionGate(
                    name="minimum_confluence",
                    status=GateStatus.PASS,
                    reason=(
                        f"Confluence {confluence_score:.3f} "
                        "meets minimum threshold."
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="minimum_confluence",
                    status=GateStatus.FAIL,
                    reason=(
                        f"Confluence {confluence_score:.3f} "
                        "is below minimum threshold."
                    ),
                )
            )

            rejections.append(
                RejectionReason.LOW_CONFLUENCE
            )

        # -------------------------------------------------
        # Reliability
        # -------------------------------------------------

        reliable_count = sum(
            item.reliability
            >= self.thresholds.minimum_reliability
            for item in evidence
        )

        if reliable_count >= self.thresholds.minimum_evidence:

            gates.append(
                DecisionGate(
                    name="evidence_reliability",
                    status=GateStatus.PASS,
                    reason=(
                        f"{reliable_count} reliable evidence items."
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="evidence_reliability",
                    status=GateStatus.WARNING,
                    reason=(
                        "Not enough high-reliability evidence."
                    ),
                )
            )

        # -------------------------------------------------
        # Conflict ratio
        # -------------------------------------------------

        bullish = sum(
            item.polarity == EvidencePolarity.BULLISH
            for item in evidence
        )

        bearish = sum(
            item.polarity == EvidencePolarity.BEARISH
            for item in evidence
        )

        directional = bullish + bearish

        if directional == 0:

            conflict_ratio = 1.0

        else:

            conflict_ratio = (
                min(bullish, bearish)
                / directional
            )

        if (
            conflict_ratio
            <= self.thresholds.maximum_conflict_ratio
        ):

            gates.append(
                DecisionGate(
                    name="conflict_ratio",
                    status=GateStatus.PASS,
                    reason=(
                        f"Conflict ratio {conflict_ratio:.3f}."
                    ),
                )
            )

        else:

            gates.append(
                DecisionGate(
                    name="conflict_ratio",
                    status=GateStatus.FAIL,
                    reason=(
                        f"Conflict ratio {conflict_ratio:.3f} "
                        "is too high."
                    ),
                )
            )

            rejections.append(
                RejectionReason.BEARISH_CONFLICT
            )

        # -------------------------------------------------
        # Hypothesis
        # -------------------------------------------------

        if hypothesis_polarity == EvidencePolarity.NEUTRAL:

            gates.append(
                DecisionGate(
                    name="directional_hypothesis",
                    status=GateStatus.FAIL,
                    reason="No directional hypothesis.",
                )
            )

            rejections.append(
                RejectionReason.INVALID_CONTEXT
            )

        else:

            gates.append(
                DecisionGate(
                    name="directional_hypothesis",
                    status=GateStatus.PASS,
                    reason=(
                        f"Hypothesis is "
                        f"{hypothesis_polarity.value}."
                    ),
                )
            )

        return GateEvaluation(
            gates=tuple(gates),
            rejection_reasons=tuple(
                dict.fromkeys(rejections)
            ),
        )
