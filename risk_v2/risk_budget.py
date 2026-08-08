from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskBudgetResult:
    allowed: bool

    risk_amount: float

    risk_percent: float

    reason: str


def evaluate_risk_budget(
    *,
    account_equity: float,
    risk_percent: float,
    maximum_risk_percent: float,
) -> RiskBudgetResult:

    if account_equity <= 0:
        return RiskBudgetResult(
            allowed=False,
            risk_amount=0.0,
            risk_percent=risk_percent,
            reason=(
                "Account equity must be positive."
            ),
        )

    if risk_percent < 0:
        return RiskBudgetResult(
            allowed=False,
            risk_amount=0.0,
            risk_percent=risk_percent,
            reason=(
                "Risk percentage cannot be negative."
            ),
        )

    risk_amount = (
        account_equity
        * risk_percent
        / 100.0
    )

    if risk_percent > maximum_risk_percent:
        return RiskBudgetResult(
            allowed=False,
            risk_amount=risk_amount,
            risk_percent=risk_percent,
            reason=(
                "Requested risk exceeds the "
                "configured risk budget."
            ),
        )

    return RiskBudgetResult(
        allowed=True,
        risk_amount=risk_amount,
        risk_percent=risk_percent,
        reason="Risk budget is within limits.",
    )
