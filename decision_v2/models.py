from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .enums import (
    DecisionAction,
    DecisionDirection,
    DecisionGrade,
    EntryType,
    GateStatus,
    RejectionReason,
)


@dataclass(frozen=True, slots=True)
class DecisionGate:
    name: str
    status: GateStatus
    reason: str
    weight: float = 1.0


@dataclass(frozen=True, slots=True)
class DecisionResult:
    action: DecisionAction
    direction: DecisionDirection

    grade: DecisionGrade

    confidence: float
    confluence_score: float

    entry_type: EntryType

    gates: tuple[DecisionGate, ...]

    rejection_reasons: tuple[RejectionReason, ...]

    supporting_evidence: tuple[str, ...]
    conflicting_evidence: tuple[str, ...]

    explanation: str

    decision_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    metadata: dict[str, object] = field(
        default_factory=dict
    )

    @property
    def accepted(self) -> bool:
        return self.action == DecisionAction.ACCEPT
