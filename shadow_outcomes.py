from __future__ import annotations

import json
import math
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


class OutcomeDirection(str, Enum):
    LONG = "long"
    SHORT = "short"

    @classmethod
    def normalize(cls, value: str | None) -> "OutcomeDirection":
        aliases = {
            "buy": cls.LONG,
            "bullish": cls.LONG,
            "long": cls.LONG,
            "sell": cls.SHORT,
            "bearish": cls.SHORT,
            "short": cls.SHORT,
        }
        try:
            return aliases[str(value or "long").strip().lower()]
        except KeyError as exc:
            raise ValueError(
                "direction must be one of: long, short, buy, sell, bullish, bearish"
            ) from exc


class ShadowOutcomeValidationError(ValueError):
    """Raised when an outcome or market bar violates tracking invariants."""


def _finite(value: Any, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ShadowOutcomeValidationError(f"{name} must be numeric") from exc
    if not math.isfinite(number):
        raise ShadowOutcomeValidationError(f"{name} must be finite")
    return number


def _optional_finite(value: Any, name: str) -> float | None:
    return None if value is None else _finite(value, name)


@dataclass
class ShadowOutcome:
    signal_id: str
    symbol: str
    timeframe: str
    strategy: str
    entry: float
    stop_loss: float
    direction: OutcomeDirection = OutcomeDirection.LONG
    target_1: float | None = None
    target_2: float | None = None
    target_3: float | None = None
    target_4: float | None = None
    macro_target: float | None = None
    status: OutcomeStatus = OutcomeStatus.PENDING
    entry_time: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    exit_time: str | None = None
    exit_price: float | None = None
    r_multiple: float | None = None
    bars_observed: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def resolved(self) -> bool:
        return self.status != OutcomeStatus.PENDING


class ShadowOutcomeTracker:
    def __init__(self, storage_path: str = "shadow_outcomes.json") -> None:
        self.storage_path = storage_path
        self.outcomes: dict[str, ShadowOutcome] = {}
        self.load()

    def load(self) -> None:
        if not os.path.exists(self.storage_path):
            return
        try:
            with open(self.storage_path, "r", encoding="utf-8") as handle:
                data = json.load(handle)
            if not isinstance(data, list):
                raise ValueError("shadow outcome storage must contain a JSON list")
            loaded: dict[str, ShadowOutcome] = {}
            for item in data:
                if not isinstance(item, dict) or "signal_id" not in item:
                    continue
                normalized = dict(item)
                normalized["status"] = OutcomeStatus(normalized.get("status", "pending"))
                normalized["direction"] = OutcomeDirection.normalize(normalized.get("direction", "long"))
                normalized["metadata"] = dict(normalized.get("metadata") or {}) if isinstance(normalized.get("metadata") or {}, dict) else {}
                loaded[str(normalized["signal_id"])] = ShadowOutcome(**normalized)
            self.outcomes = loaded
        except (OSError, json.JSONDecodeError, TypeError, KeyError, ValueError):
            self.outcomes = {}

    def save(self) -> None:
        payload = []
        for outcome in self.outcomes.values():
            item = asdict(outcome)
            item["status"] = outcome.status.value
            item["direction"] = outcome.direction.value
            payload.append(item)
        directory = os.path.dirname(self.storage_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        temporary_path = f"{self.storage_path}.tmp"
        with open(temporary_path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, default=str)
        os.replace(temporary_path, self.storage_path)

    def register(
        self,
        *,
        signal_id: str,
        symbol: str,
        timeframe: str,
        strategy: str,
        entry: float,
        stop_loss: float,
        direction: str | OutcomeDirection = OutcomeDirection.LONG,
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

        normalized_direction = OutcomeDirection.normalize(
            direction.value if isinstance(direction, OutcomeDirection) else direction
        )
        normalized_entry = _finite(entry, "entry")
        normalized_stop = _finite(stop_loss, "stop_loss")
        if normalized_direction == OutcomeDirection.LONG and normalized_stop >= normalized_entry:
            raise ShadowOutcomeValidationError("long outcome requires stop_loss below entry")
        if normalized_direction == OutcomeDirection.SHORT and normalized_stop <= normalized_entry:
            raise ShadowOutcomeValidationError("short outcome requires stop_loss above entry")

        targets = [
            _optional_finite(target_1, "target_1"),
            _optional_finite(target_2, "target_2"),
            _optional_finite(target_3, "target_3"),
            _optional_finite(target_4, "target_4"),
            _optional_finite(macro_target, "macro_target"),
        ]
        present = [value for value in targets if value is not None]
        if normalized_direction == OutcomeDirection.LONG:
            if any(value <= normalized_entry for value in present):
                raise ShadowOutcomeValidationError("long targets must be above entry")
            if any(current <= previous for previous, current in zip(present, present[1:])):
                raise ShadowOutcomeValidationError("long targets must be strictly increasing")
        else:
            if any(value >= normalized_entry for value in present):
                raise ShadowOutcomeValidationError("short targets must be below entry")
            if any(current >= previous for previous, current in zip(present, present[1:])):
                raise ShadowOutcomeValidationError("short targets must be strictly decreasing")

        outcome = ShadowOutcome(
            signal_id=str(signal_id),
            symbol=str(symbol),
            timeframe=str(timeframe),
            strategy=str(strategy),
            entry=normalized_entry,
            stop_loss=normalized_stop,
            direction=normalized_direction,
            target_1=targets[0],
            target_2=targets[1],
            target_3=targets[2],
            target_4=targets[3],
            macro_target=targets[4],
            metadata=dict(metadata or {}),
        )
        self.outcomes[outcome.signal_id] = outcome
        self.save()
        return outcome

    def process_bar(
        self,
        *,
        signal_id: str,
        high: float,
        low: float,
        timestamp: str | None = None,
    ) -> ShadowOutcome | None:
        outcome = self.outcomes.get(signal_id)
        if outcome is None or outcome.resolved:
            return outcome

        normalized_high = _finite(high, "high")
        normalized_low = _finite(low, "low")
        if normalized_low > normalized_high:
            raise ShadowOutcomeValidationError("bar low cannot be greater than bar high")

        outcome.bars_observed += 1
        stop_hit = (
            normalized_low <= outcome.stop_loss
            if outcome.direction == OutcomeDirection.LONG
            else normalized_high >= outcome.stop_loss
        )
        if stop_hit:
            self._resolve(outcome, OutcomeStatus.STOPPED, outcome.stop_loss, timestamp)
            return outcome

        targets = [
            (OutcomeStatus.TARGET_1, outcome.target_1),
            (OutcomeStatus.TARGET_2, outcome.target_2),
            (OutcomeStatus.TARGET_3, outcome.target_3),
            (OutcomeStatus.TARGET_4, outcome.target_4),
            (OutcomeStatus.MACRO_TARGET, outcome.macro_target),
        ]
        for status, level in targets:
            if level is not None and normalized_low <= level <= normalized_high:
                self._resolve(outcome, status, level, timestamp)
                return outcome

        self.save()
        return outcome

    def expire(self, signal_id: str, timestamp: str | None = None) -> ShadowOutcome | None:
        outcome = self.outcomes.get(signal_id)
        if outcome is None or outcome.resolved:
            return outcome
        self._resolve(outcome, OutcomeStatus.EXPIRED, outcome.entry, timestamp)
        return outcome

    def _resolve(
        self,
        outcome: ShadowOutcome,
        status: OutcomeStatus,
        exit_price: float,
        timestamp: str | None,
    ) -> None:
        if outcome.resolved:
            return
        exit_value = _finite(exit_price, "exit_price")
        outcome.status = status
        outcome.exit_price = exit_value
        outcome.exit_time = timestamp or datetime.now(timezone.utc).isoformat()
        risk = abs(outcome.entry - outcome.stop_loss)
        if risk > 0:
            outcome.r_multiple = (
                (exit_value - outcome.entry) / risk
                if outcome.direction == OutcomeDirection.LONG
                else (outcome.entry - exit_value) / risk
            )
        self.save()

    def pending(self) -> list[ShadowOutcome]:
        return [item for item in self.outcomes.values() if not item.resolved]

    def resolved(self) -> list[ShadowOutcome]:
        return [item for item in self.outcomes.values() if item.resolved]

    def summary(self) -> dict[str, Any]:
        resolved = self.resolved()
        measurable = [item for item in resolved if item.r_multiple is not None]
        wins = [item for item in measurable if item.r_multiple > 0]
        losses = [item for item in measurable if item.r_multiple <= 0]
        positive_r = sum(item.r_multiple for item in wins)
        negative_r = sum(item.r_multiple for item in losses)
        return {
            "total": len(self.outcomes),
            "pending": len(self.pending()),
            "resolved": len(resolved),
            "wins": len(wins),
            "losses": len(losses),
            "win_rate": len(wins) / len(measurable) if measurable else 0.0,
            "average_r": sum(item.r_multiple for item in measurable) / len(measurable) if measurable else 0.0,
            "profit_factor": positive_r / abs(negative_r) if negative_r < 0 else float("inf") if positive_r > 0 else 0.0,
            "by_status": {
                status.value: sum(1 for item in self.outcomes.values() if item.status == status)
                for status in OutcomeStatus
            },
        }
