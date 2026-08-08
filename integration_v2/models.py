from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .enums import ExecutionMode


@dataclass(frozen=True, slots=True)
class AuditEvent:
    event_type: str
    symbol: str
    mode: ExecutionMode
    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    payload: dict[str, Any] = field(default_factory=dict)
    event_id: str = field(
        default_factory=lambda: str(uuid4())
    )


@dataclass(frozen=True, slots=True)
class IntegrationResult:
    mode: ExecutionMode
    decision: Any
    eligibility: Any
    trade: Any | None = None
    audit_event_id: str | None = None

    @property
    def executable(self) -> bool:
        return self.trade is not None
