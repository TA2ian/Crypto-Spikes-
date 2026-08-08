from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class OutcomeStatus(str, Enum):
    PENDING = "pending"
    STOPPED = "stopped"
    TARGET_1 = "target_1"
    TARGET_2 = "target_2"
    TARGET_3 = "target_3"
    TARGET_4 = "target_4"
    MACRO_TARGET = "macro_target"
    EXPIRED = "expired"


@dataclass
class ShadowOutcome:
    signal_id: str
    symbol: str
    timeframe: str
    strategy: str

    entry: float
    stop_loss: float

    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    target_4: float | None = None
    macro_target: float | None = None

    status: OutcomeStatus = OutcomeStatus.PENDING

    entry_time: str = field(
        default_factory=lambda:
        datetime.now(timezone.utc).isoformat()
    )

    exit_time: str | None = None
    exit_price: float | None = None
    r_multiple: float | None = None

    bars_observed: int = 0
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def resolved(self) -> bool:
        return self.status != OutcomeStatus.PENDING


class ShadowOutcomeTracker:

    def __init__(
        self,
        storage_path: str = "shadow_outcomes.json",
    ) -> None:
        self.storage_path = storage_path
        self.outcomes: dict[str, ShadowOutcome] = {}
        self.load()

    # --------------------------------------------------
    # Persistence
    # --------------------------------------------------

    def load(self) -> None:
        if not os.path.exists(self.storage_path):
            return

        try:
            with open(
                self.storage_path,
                "r",
                encoding="utf-8",
            ) as handle:
                data = json.load(handle)

            for item in data:
                item["status"] = OutcomeStatus(
                    item["status"]
                )

                self.outcomes[
                    item["signal_id"]
                ] = ShadowOutcome(**item)

        except (
            OSError,
            ValueError,
            TypeError,
            KeyError,
        ):
            self.outcomes = {}

    def save(self) -> None:
        payload = []

        for outcome in self.outcomes.values():
            item = asdict(outcome)
            item["status"] = outcome.status.value
            payload.append(item)

        directory = os.path.dirname(
            self.storage_path
        )

        if directory:
            os.makedirs(
                directory,
                exist_ok=True,
            )

        with open(
            self.storage_path,
            "w",
            encoding="utf-8",
        ) as handle:
            json.dump(
                payload,
                handle,
                ensure_ascii=False,
                indent=2,
                default=str,
            )

    # --------------------------------------------------
    # Registration
    # --------------------------------------------------

    def register(
        self,
        *,
        signal_id: str,
        symbol: str,
        timeframe: str,
        strategy: str,
        entry: float,
        stop_loss: float,
        target_1: float | None = None,
        target_2: float | None = None,
        target_3: float | None = None,
        target_4: float | None = None,
        macro_target: float | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ShadowOutcome:

        existing = self.outcomes.get(signal_id)

        if existing is not None:
            return existing

        outcome = ShadowOutcome(
            signal_id=signal_id,
            symbol=symbol,
            timeframe=timeframe,
            strategy=strategy,
            entry=float(entry),
            stop_loss=float(stop_loss),
            target_1=(
                float(target_1)
                if target_1 is not None
                else None
            ),
            target_2=(
                float(target_2)
                if target_2 is not None
                else None
            ),
            target_3=(
                float(target_3)
                if target_3 is not None
                else None
            ),
            target_4=(
                float(target_4)
                if target_4 is not None
                else None
            ),
            macro_target=(
                float(macro_target)
                if macro_target is not None
                else None
            ),
            metadata=metadata or {},
        )

        self.outcomes[signal_id] = outcome
        self.save()

        return outcome

    # --------------------------------------------------
    # Real candle observation
    # --------------------------------------------------

    def process_bar(
        self,
        *,
        signal_id: str,
        high: float,
        low: float,
        timestamp: str | None = None,
    ) -> ShadowOutcome | None:

        outcome = self.outcomes.get(signal_id)

        if outcome is None:
            return None

        if outcome.resolved:
            return outcome

        outcome.bars_observed += 1

        high = float(high)
        low = float(low)

        # Conservative rule:
        # If SL and TP are touched in the same candle,
        # SL is assumed to have happened first.
        if low <= outcome.stop_loss:
            self._resolve(
                outcome=outcome,
                status=OutcomeStatus.STOPPED,
                exit_price=outcome.stop_loss,
                timestamp=timestamp,
            )
            return outcome

        targets = [
            (
                OutcomeStatus.TARGET_1,
                outcome.target_1,
            ),
            (
                OutcomeStatus.TARGET_2,
                outcome.target_2,
            ),
            (
                OutcomeStatus.TARGET_3,
                outcome.target_3,
            ),
            (
                OutcomeStatus.TARGET_4,
                outcome.target_4,
            ),
            (
                OutcomeStatus.MACRO_TARGET,
                outcome.macro_target,
            ),
        ]

        reached = [
            (status, level)
            for status, level in targets
            if level is not None
            and high >= level
        ]

        if reached:
            status, price = reached[-1]

            self._resolve(
                outcome=outcome,
                status=status,
                exit_price=price,
                timestamp=timestamp,
            )
        else:
            self.save()

        return outcome

    def expire(
        self,
        signal_id: str,
        timestamp: str | None = None,
    ) -> ShadowOutcome | None:

        outcome = self.outcomes.get(signal_id)

        if outcome is None:
            return None

        if outcome.resolved:
            return outcome

        self._resolve(
            outcome=outcome,
            status=OutcomeStatus.EXPIRED,
            exit_price=outcome.entry,
            timestamp=timestamp,
        )

        return outcome

    # --------------------------------------------------
    # Resolution
    # --------------------------------------------------

    def _resolve(
        self,
        *,
        outcome: ShadowOutcome,
        status: OutcomeStatus,
        exit_price: float,
        timestamp: str | None,
    ) -> None:

        outcome.status = status
        outcome.exit_price = float(exit_price)

        outcome.exit_time = (
            timestamp
            or datetime.now(
                timezone.utc
            ).isoformat()
        )

        risk = abs(
            outcome.entry
            - outcome.stop_loss
        )

        if risk > 0:
            outcome.r_multiple = (
                outcome.exit_price
                - outcome.entry
            ) / risk

        self.save()

    # --------------------------------------------------
    # Collections
    # --------------------------------------------------

    def pending(self) -> list[ShadowOutcome]:
        return [
            item
            for item in self.outcomes.values()
            if not item.resolved
        ]

    def resolved(self) -> list[ShadowOutcome]:
        return [
            item
            for item in self.outcomes.values()
            if item.resolved
        ]

    # --------------------------------------------------
    # Performance report
    # --------------------------------------------------

    def summary(self) -> dict[str, Any]:

        resolved = self.resolved()

        wins = [
            item
            for item in resolved
            if item.r_multiple is not None
            and item.r_multiple > 0
        ]

        losses = [
            item
            for item in resolved
            if item.r_multiple is not None
            and item.r_multiple <= 0
        ]

        positive_r = sum(
            item.r_multiple
            for item in wins
            if item.r_multiple is not None
        )

        negative_r = sum(
            item.r_multiple
            for item in losses
            if item.r_multiple is not None
        )

        average_r = (
            sum(
                item.r_multiple
                for item in resolved
                if item.r_multiple is not None
            )
            / len(resolved)
            if resolved
            else 0.0
        )

        profit_factor = (
            positive_r / abs(negative_r)
            if negative_r < 0
            else (
                float("inf")
                if positive_r > 0
                else 0.0
            )
        )

        by_status = {
            status.value: sum(
                1
                for item in self.outcomes.values()
                if item.status == status
            )
            for status in OutcomeStatus
        }

        return {
            "total": len(self.outcomes),
            "pending": len(self.pending()),
            "resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": (
                len(wins) / len(resolved)
                if resolved
                else 0.0
            ),
            "average_r": average_r,
            "profit_factor": profit_factor,
            "by_status": by_status,
        }
