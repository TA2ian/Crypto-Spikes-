from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
)
from integration_v2 import (
    ExecutionMode,
    V2Pipeline,
)
from risk_v2 import (
    RiskParameters,
    StrategyType,
)
from shadow_outcome_integration import (
    ShadowOutcomeIntegration,
)


LEGACY_TO_V2_STRATEGY = {
    "WYCKOFF_SMC_ACCUMULATION": StrategyType.WYCKOFF_SMC,
    "CVD_BREAKOUT_CONFIRMED": StrategyType.CVD_SQUEEZE,
    "TREND_FOLLOWING_4_CONFIRMS": StrategyType.TREND_FOLLOWING,
    "MEAN_REVERSION_4_CONFIRMS": StrategyType.MEAN_REVERSION,
    "CHART_PATTERN_4_CONFIRMS": StrategyType.CHART_PATTERN,
    "FVG_SCALP_4_CONFIRMS": StrategyType.FVG_SCALP,
    "ULTIMATE_MASTER_A_PLUS": StrategyType.ULTIMATE_A_PLUS,
    "CAPITULATION_RE_ENTRY": StrategyType.CAPITULATION,
}


def _category_for_note(
    note: str,
) -> EvidenceCategory:
    text = note.lower()

    if "diverg" in text or "دايفرجنس" in text:
        return EvidenceCategory.DIVERGENCE

    if "fvg" in text:
        return EvidenceCategory.SMC

    if "order block" in text:
        return EvidenceCategory.SMC

    if "liquidity" in text or "سيولة" in text:
        return EvidenceCategory.LIQUIDITY

    if "bos" in text or "choch" in text or "هيكل" in text:
        return EvidenceCategory.STRUCTURE

    if "volume" in text or "فوليوم" in text or "جهد" in text:
        return EvidenceCategory.VOLUME

    if "ema" in text or "اتجاه" in text:
        return EvidenceCategory.TREND

    if "bollinger" in text or "بولينجر" in text:
        return EvidenceCategory.VOLATILITY

    if "pattern" in text or "نمط" in text:
        return EvidenceCategory.PATTERN

    if "rsi" in text or "dpr" in text:
        return EvidenceCategory.MOMENTUM

    return EvidenceCategory.STRUCTURE


def _evidence_from_signal(
    signal: dict[str, Any],
) -> list[EvidenceRecord]:
    notes = signal.get("confluence") or []

    if not isinstance(notes, list):
        notes = [str(notes)]

    evidence: list[EvidenceRecord] = []

    for note in notes:
        name = str(note).strip()

        if not name:
            continue

        evidence.append(
            EvidenceRecord(
                category=_category_for_note(name),
                polarity=EvidencePolarity.BULLISH,
                name=name,
                strength=1.0,
                reliability=0.80,
                freshness=1.0,
                timeframe=str(
                    signal.get(
                        "timeframe",
                        "1h",
                    )
                ),
                source="legacy_scanner_shadow",
            )
        )

    return evidence


def _confluence_score(
    evidence: Iterable[EvidenceRecord],
) -> float:
    evidence_list = list(evidence)

    return min(
        1.0,
        len(evidence_list) / 5.0,
    )


def _risk_reward(
    signal: dict[str, Any],
) -> float:
    entry = float(
        signal["price"]
    )

    stop = float(
        signal["stop_loss"]
    )

    target = float(
        signal.get("target2")
        or signal.get("target1")
        or entry
    )

    risk = abs(
        entry - stop
    )

    if risk <= 0:
        return 0.0

    return abs(
        target - entry
    ) / risk


def _halal_from_watchlist(
    symbol: str,
    watchlist: Iterable[str],
) -> bool:
    normalized = (
        symbol
        .upper()
        .replace("/", "-")
    )

    return normalized in {
        str(item)
        .upper()
        .replace("/", "-")
        for item in watchlist
    }


class ScannerShadowBridge:
    """
    Runs V2 beside the legacy scanner without changing
    legacy execution behavior.

    SHADOW mode never creates a TradeState
    and never submits orders.

    Accepted V2 signals are registered with the
    ShadowOutcomeIntegration layer for later
    outcome tracking.
    """

    def __init__(
        self,
        *,
        watchlist: Iterable[str],
    ) -> None:
        self.pipeline = V2Pipeline(
            mode=ExecutionMode.SHADOW
        )

        self.watchlist = tuple(
            watchlist
        )

        self.outcome_integration = (
            ShadowOutcomeIntegration()
        )

    def evaluate(
        self,
        *,
        signal: dict[str, Any],
        strategy_type: str,
        macro_info: dict[str, Any],
        active_positions: int,
        account_equity: float,
        risk_percent: float,
    ):
        strategy = LEGACY_TO_V2_STRATEGY.get(
            strategy_type
        )

        if strategy is None:
            return None

        evidence = _evidence_from_signal(
            signal
        )

        if not evidence:
            return None

        confluence_score = _confluence_score(
            evidence
        )

        entry = float(
            signal["price"]
        )

        stop = float(
            signal["stop_loss"]
        )

        symbol = str(
            signal["symbol"]
        )

        asset_supported = _halal_from_watchlist(
            symbol,
            self.watchlist,
        )

        macro_bullish = bool(
            macro_info.get(
                "macro_bullish",
                False,
            )
        )

        target1 = signal.get("target1")
        target2 = signal.get("target2")
        target3 = signal.get("target3")
        target4 = signal.get("target4")

        result = self.pipeline.evaluate(
            # --------------------------------------------------
            # Asset
            # --------------------------------------------------
            symbol=symbol,
            asset_supported=asset_supported,

            # --------------------------------------------------
            # Strategy
            # --------------------------------------------------
            strategies=[strategy],

            # --------------------------------------------------
            # Evidence / decision inputs
            # --------------------------------------------------
            evidence=evidence,
            confluence_score=confluence_score,
            hypothesis_polarity=(
                EvidencePolarity.BULLISH
            ),

            # --------------------------------------------------
            # Entry / Stop / Targets
            # --------------------------------------------------
            entry=entry,
            stop_loss=stop,
            targets=(
                target1,
                target2,
                target3,
                target4,
            ),

            # --------------------------------------------------
            # Risk
            # --------------------------------------------------
            risk=RiskParameters(
                entry_price=entry,
                stop_loss=stop,
                target_1=target1,
                target_2=target2,
                target_3=target3,
                target_4=target4,
                account_equity=account_equity,
                risk_percent=risk_percent,
            ),

            # --------------------------------------------------
            # Position / Macro context
            # --------------------------------------------------
            active_positions=active_positions,
            htf_bullish=macro_bullish,
            macro_bullish=macro_bullish,

            # --------------------------------------------------
            # Risk / Halal eligibility
            # --------------------------------------------------
            risk_reward_value=_risk_reward(
                signal
            ),
            halal_eligible=asset_supported,

            # --------------------------------------------------
            # Audit metadata
            # --------------------------------------------------
            metadata={
                "legacy_strategy": strategy_type,
                "legacy_signal_type": signal.get(
                    "type"
                ),
                "legacy_signal_status": signal.get(
                    "signal_status"
                ),
                "legacy_stars": signal.get(
                    "stars"
                ),
                "timeframe": signal.get(
                    "timeframe"
                ),
                "entry": entry,
                "stop_loss": stop,
            },
        )

        # --------------------------------------------------
        # Shadow Outcome Registration
        #
        # Observation-only.
        # Never opens, modifies, or submits a real trade.
        # --------------------------------------------------
        self.outcome_integration.register_if_accepted(
            signal=signal,
            strategy_type=strategy_type,
            result=result,
        )

        return result


def compare_legacy_and_v2(
    *,
    legacy_strategy: str,
    result: Any,
) -> dict[str, Any]:
    if result is None:
        return {
            "status": (
                "unmapped_or_insufficient_evidence"
            ),
            "legacy_strategy": legacy_strategy,
        }

    v2_accept = bool(
        result.decision.accepted
    )

    return {
        "status": (
            "agreement"
            if v2_accept
            else "v2_reject"
        ),
        "legacy_strategy": legacy_strategy,
        "v2_action": (
            result.decision.action.value
        ),
        "v2_grade": (
            result.decision.grade.value
        ),
        "v2_confidence": (
            result.decision.confidence
        ),
        "v2_eligibility": (
            result.eligibility.status.value
        ),
        "v2_blocked_reasons": [
            reason.value
            for reason
            in result.eligibility.blocked_reasons
        ],
        "v2_strategy_eligible": [
            strategy.value
            for strategy
            in result.eligibility.eligible_strategies
        ],
        "audit_event_id": (
            result.audit_event_id
        ),
    }
