from __future__ import annotations

from decision_v2 import DecisionResult
from risk_v2 import EligibilityResult

from .enums import Direction
from .manager import TradeManager
from .models import TradeState


def create_trade_from_analysis(
    *,
    decision: DecisionResult,
    eligibility: EligibilityResult,
    manager: TradeManager,
    entry: float,
    stop_loss: float,
    target_1: float | None = None,
    target_2: float | None = None,
    target_3: float | None = None,
    target_4: float | None = None,
) -> TradeState:

    if not decision.accepted:
        raise ValueError(
            "Decision was not accepted."
        )

    if not eligibility.eligible:
        raise ValueError(
            "Trade is not risk eligible."
        )

    if decision.direction.value == "long":
        direction = Direction.LONG

    elif decision.direction.value == "short":
        direction = Direction.SHORT

    else:
        raise ValueError(
            "Cannot create trade from neutral direction."
        )

    return manager.create_trade(
        direction=direction,
        entry=entry,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        target_3=target_3,
        target_4=target_4,
    )
