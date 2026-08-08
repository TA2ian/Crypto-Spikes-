from __future__ import annotations

from collections.abc import Sequence

from .atr import atr_percent
from .enums import (
    RiskBlockReason,
)
from .models import (
    RiskCheck,
    RiskParameters,
)
from .risk_budget import evaluate_risk_budget
from .thresholds import RiskThresholds


class EligibilityGates:

    def __init__(
        self,
        thresholds: RiskThresholds,
    ) -> None:

        self.thresholds = thresholds

    def evaluate(
        self,
        *,
        risk: RiskParameters,
        active_positions: int,
        htf_bullish: bool,
        macro_bullish: bool,
        risk_reward_value: float,
        halal_eligible: bool,
        asset_supported: bool,
    ) -> tuple[
        tuple[RiskCheck, ...],
        tuple[RiskBlockReason, ...],
    ]:

        checks: list[RiskCheck] = []
        blocked: list[RiskBlockReason] = []

        # -------------------------------------------------
        # Halal eligibility
        # -------------------------------------------------

        checks.append(
            RiskCheck(
                name="halal_eligibility",
                passed=halal_eligible,
                reason=(
                    "Asset is halal eligible."
                    if halal_eligible
                    else
                    "Asset is not halal eligible."
                ),
            )
        )

        if not halal_eligible:
            blocked.append(
                RiskBlockReason.HALAL_INELIGIBLE
            )

        # -------------------------------------------------
        # Asset support
        # -------------------------------------------------

        checks.append(
            RiskCheck(
                name="asset_supported",
                passed=asset_supported,
                reason=(
                    "Asset is supported."
                    if asset_supported
                    else
                    "Asset is not supported."
                ),
            )
        )

        if not asset_supported:
            blocked.append(
                RiskBlockReason.ASSET_NOT_SUPPORTED
            )

        # -------------------------------------------------
        # Active positions
        # -------------------------------------------------

        positions_ok = (
            active_positions
            < self.thresholds.maximum_active_positions
        )

        checks.append(
            RiskCheck(
                name="active_positions",
                passed=positions_ok,
                value=float(active_positions),
                threshold=float(
                    self.thresholds.maximum_active_positions
                ),
                reason=(
                    "Active position count is within limits."
                    if positions_ok
                    else
                    "Maximum active position count reached."
                ),
            )
        )

        if not positions_ok:
            blocked.append(
                RiskBlockReason.ACTIVE_TRADE_CONFLICT
            )

        # -------------------------------------------------
        # HTF alignment
        # -------------------------------------------------

        checks.append(
            RiskCheck(
                name="htf_alignment",
                passed=htf_bullish,
                reason=(
                    "HTF trend is aligned."
                    if htf_bullish
                    else
                    "HTF trend conflicts with the bullish setup."
                ),
            )
        )

        if not htf_bullish:
            blocked.append(
                RiskBlockReason.HTF_CONFLICT
            )

        # -------------------------------------------------
        # Macro alignment
        # -------------------------------------------------

        checks.append(
            RiskCheck(
                name="macro_alignment",
                passed=macro_bullish,
                reason=(
                    "Macro trend is aligned."
                    if macro_bullish
                    else
                    "Macro trend conflicts with the setup."
                ),
            )
        )

        if not macro_bullish:
            blocked.append(
                RiskBlockReason.MACRO_CONFLICT
            )

        # -------------------------------------------------
        # R/R
        # -------------------------------------------------

        rr_ok = (
            risk_reward_value
            >= self.thresholds.minimum_rr
        )

        checks.append(
            RiskCheck(
                name="risk_reward",
                passed=rr_ok,
                value=risk_reward_value,
                threshold=self.thresholds.minimum_rr,
                reason=(
                    "Risk/reward meets minimum."
                    if rr_ok
                    else
                    "Risk/reward is insufficient."
                ),
            )
        )

        if not rr_ok:
            blocked.append(
                RiskBlockReason.INSUFFICIENT_RR
            )

        # -------------------------------------------------
        # Risk budget
        # -------------------------------------------------

        budget = evaluate_risk_budget(
            account_equity=risk.account_equity,
            risk_percent=risk.risk_percent,
            maximum_risk_percent=(
                self.thresholds.maximum_risk_percent
            ),
        )

        checks.append(
            RiskCheck(
                name="risk_budget",
                passed=budget.allowed,
                value=risk.risk_percent,
                threshold=(
                    self.thresholds.maximum_risk_percent
                ),
                reason=budget.reason,
            )
        )

        if not budget.allowed:
            blocked.append(
                RiskBlockReason.RISK_BUDGET_EXCEEDED
            )

        # -------------------------------------------------
        # ATR volatility
        # -------------------------------------------------

        if risk.atr is not None:

            volatility = atr_percent(
                atr=risk.atr,
                price=risk.entry_price,
            )

            volatility_ok = (
                self.thresholds.minimum_atr_percent
                <= volatility
                <= self.thresholds.maximum_atr_percent
            )

            checks.append(
                RiskCheck(
                    name="atr_volatility",
                    passed=volatility_ok,
                    value=volatility,
                    reason=(
                        "ATR volatility is acceptable."
                        if volatility_ok
                        else
                        "ATR volatility is outside limits."
                    ),
                )
            )

            if not volatility_ok:

                if (
                    volatility
                    > self.thresholds.maximum_atr_percent
                ):
                    blocked.append(
                        RiskBlockReason.VOLATILITY_TOO_HIGH
                    )

                else:
                    blocked.append(
                        RiskBlockReason.VOLATILITY_TOO_LOW
                    )

        return (
            tuple(checks),
            tuple(
                dict.fromkeys(blocked)
            ),
        )
