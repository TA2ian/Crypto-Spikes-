"""
Decision domain model.

A Decision represents the system's evaluated action after considering
supporting and conflicting evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4
from typing import Any


class DecisionAction(str, Enum):
    NO_ACTION = "no_action"
    WATCH = "watch"
    BUY = "buy"
    SELL = "sell"
    EXIT = "exit"
    REDUCE = "reduce"
    REENTER = "reenter"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"
    UNKNOWN = "unknown"


@dataclass(slots=True)
class Decision:
    """
    A traceable trading decision.

    Evidence IDs are stored rather than embedding the full Evidence
    objects to keep the decision model lightweight.
    """

    action: DecisionAction
    confidence: float
    risk_level: RiskLevel

    evidence_ids: list[str] = field(default_factory=list)

    supporting_evidence: list[str] = field(default_factory=list)
    conflicting_evidence: list[str] = field(default_factory=list)

    strategy: str | None = None
    reasoning: str = ""

    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    expires_at: datetime | None = None

    decision_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError(
                "confidence must be between 0 and 1"
            )

        if not self.decision_id.strip():
            raise ValueError("decision_id cannot be empty")

        if not self.reasoning.strip() and self.action not in (
            DecisionAction.NO_ACTION,
            DecisionAction.WATCH,
        ):
            raise ValueError(
                "actionable decisions require reasoning"
            )

        self._remove_duplicate_ids()

    def _remove_duplicate_ids(self) -> None:
        self.evidence_ids = list(
            dict.fromkeys(self.evidence_ids)
        )

        self.supporting_evidence = list(
            dict.fromkeys(self.supporting_evidence)
        )

        self.conflicting_evidence = list(
            dict.fromkeys(self.conflicting_evidence)
        )

    def add_evidence(
        self,
        evidence_id: str,
        *,
        supporting: bool,
    ) -> None:
        """Attach evidence to the decision."""

        evidence_id = evidence_id.strip()

        if not evidence_id:
            raise ValueError("evidence_id cannot be empty")

        if evidence_id not in self.evidence_ids:
            self.evidence_ids.append(evidence_id)

        target = (
            self.supporting_evidence
            if supporting
            else self.conflicting_evidence
        )

        if evidence_id not in target:
            target.append(evidence_id)

    def has_conflict(self) -> bool:
        """Return True when the decision contains conflicting evidence."""

        return bool(self.conflicting_evidence)

    def is_actionable(self) -> bool:
        """Return whether the decision represents an executable action."""

        return self.action in {
            DecisionAction.BUY,
            DecisionAction.SELL,
            DecisionAction.EXIT,
            DecisionAction.REDUCE,
            DecisionAction.REENTER,
        }

    def is_expired(self) -> bool:
        """Return whether the decision has expired."""

        if self.expires_at is None:
            return False

        now = datetime.now(timezone.utc)

        expires_at = self.expires_at

        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(
                tzinfo=timezone.utc
            )

        return now >= expires_at
