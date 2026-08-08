from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import uuid4

from .enums import (
    EligibilityStatus,
    RiskBlockReason,
    RiskLevel,
    StrategyType,
)


@dataclass(frozen=True, slots=True)
class RiskParameters:
    entry_price: float
    stop_loss: float

    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    target_4: float | None = None

    account_equity: float = 0.0
    risk_percent: float = 1.0

    atr: float | None = None

    def __post_init__(self) -> None:
        if self.entry_price <= 0:
            raise ValueError(
                "entry_price must be positive"
            )

        if self.stop_loss <= 0:
            raise ValueError(
                "stop_loss must be positive"
            )

        if self.account_equity < 0:
            raise ValueError(
                "account_equity cannot be negative"
            )

        if self.risk_percent < 0:
            raise ValueError(
                "risk_percent cannot be negative"
            )

        if self.atr is not None and self.atr < 0:
            raise ValueError(
                "atr cannot be negative"
            )


@dataclass(frozen=True, slots=True)
class StrategyEligibility:
    strategy: StrategyType
    eligible: bool

    score: float

    reasons: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class RiskCheck:
    name: str
    passed: bool
    value: float | None = None
    threshold: float | None = None
    reason: str = ""


@dataclass(frozen=True, slots=True)
class EligibilityResult:
    status: EligibilityStatus

    risk_level: RiskLevel

    risk_score: float

    checks: tuple[RiskCheck, ...]

    blocked_reasons: tuple[RiskBlockReason, ...]

    eligible_strategies: tuple[StrategyType, ...]

    strategy_results: tuple[StrategyEligibility, ...]

    decision_id: str | None = None

    explanation: str = ""

    evaluation_id: str = field(
        default_factory=lambda: str(uuid4())
    )

    timestamp: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def eligible(self) -> bool:
        return (
            self.status
            == EligibilityStatus.ELIGIBLE
        )
