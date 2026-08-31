from __future__ import annotations

from threading import RLock
from typing import Any

import requests

from shadow_outcomes import ShadowOutcomeTracker


class ShadowOutcomeIntegration:
    """
    Adapter between Scanner Shadow results and ShadowOutcomeTracker.

    Observation-only: this layer never opens, modifies, or closes real trades.

    The scanner calls this object from multiple worker threads and the
    ScannerShadowBridge has its own integration instance. Both therefore use
    a shared per-storage lock and reload persisted state before writes so one
    tracker cannot overwrite another tracker's newer outcomes.
    """

    _OKX_BAR_MAP = {
        "15m": "15m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
        "3d": "3D",
        "1w": "1W",
    }

    _locks_guard = RLock()
    _storage_locks: dict[str, RLock] = {}

    @classmethod
    def _lock_for(cls, storage_path: str) -> RLock:
        key = str(storage_path)
        with cls._locks_guard:
            lock = cls._storage_locks.get(key)
            if lock is None:
                lock = RLock()
                cls._storage_locks[key] = lock
            return lock

    def __init__(
        self,
        tracker: ShadowOutcomeTracker | None = None,
    ) -> None:
        self.tracker = tracker or ShadowOutcomeTracker(
            storage_path="shadow_outcomes.json"
        )
        self._loaded_storage_path = getattr(
            self.tracker,
            "storage_path",
            None,
        )
        self._history_cache: dict[
            tuple[str, str, str],
            list[dict[str, Any]],
        ] = {}

    @staticmethod
    def build_signal_id(
        signal: dict[str, Any],
        strategy_type: str,
    ) -> str:
        symbol = str(signal.get("symbol", "UNKNOWN"))
        timeframe = str(signal.get("timeframe", "UNKNOWN"))
        entry = float(signal.get("price", 0.0))
        direction = str(
            signal.get("direction", signal.get("side", "long"))
        ).strip().lower()
        return f"{symbol}-{timeframe}-{strategy_type}-{direction}-{entry:.8f}"

    @staticmethod
    def _read_value(
        obj: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @classmethod
    def is_shadow_accepted(cls, result: Any) -> bool:
        if result is None:
            return False

        decision = cls._read_value(result, "decision", None)
        if decision is not None:
            accepted = cls._read_value(decision, "accepted", None)

            if isinstance(accepted, bool):
                return accepted
            if isinstance(accepted, str):
                normalized = accepted.strip().lower()
                if normalized in {"true", "yes", "accept", "accepted"}:
                    return True
                if normalized in {"false", "no", "reject", "rejected", "wait"}:
                    return False

            if isinstance(decision, str):
                normalized = decision.strip().lower()
                if normalized in {"accept", "accepted"}:
                    return True
                if normalized in {"reject", "rejected", "wait"}:
                    return False
            return False

        action = cls._read_value(result, "action", None)
        if isinstance(action, str):
            normalized = action.strip().lower()
            if normalized in {"accept", "accepted"}:
                return True
            if normalized in {"reject", "rejected", "wait"}:
                return False

        return False

    def _sync_storage_context(self) -> None:
        current_path = getattr(self.tracker, "storage_path", None)
        if current_path is None:
            return

        if current_path != self._loaded_storage_path:
            self.tracker.outcomes = {}
            self._loaded_storage_path = current_path

        self.tracker.load()

    def _pending_for_market(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> bool:
        return any(
            not outcome.resolved
            and str(outcome.symbol) == str(symbol)
            and str(outcome.timeframe) == str(timeframe)
            for outcome in self.tracker.outcomes.values()
        )

    def _oldest_pending_timestamp(
        self,
        *,
        symbol: str,
        timeframe: str,
    ) -> str | None:
        timestamps: list[str] = []
        for outcome in self.tracker.outcomes.values():
            if outcome.resolved:
                continue
            if str(outcome.symbol) != str(symbol):
                continue
            if str(outcome.timeframe) != str(timeframe):
                continue
            value = (outcome.metadata or {}).get("candle_timestamp")
            if value is not None:
                timestamps.append(str(value))
        return min(timestamps) if timestamps else None

    def _fetch_completed_history(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_timestamp: str,
    ) -> list[dict[str, Any]]:
        cache_key = (str(symbol), str(timeframe), str(current_timestamp))
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]

        bar = self._OKX_BAR_MAP.get(str(timeframe))
        if bar is None:
            return []

        clean_symbol = str(symbol).replace("/", "-").upper()
        if not clean_symbol.endswith("-USDT"):
            clean_symbol = f"{clean_symbol}-USDT"

        oldest_signal = self._oldest_pending_timestamp(
            symbol=symbol,
            timeframe=timeframe,
        )

        collected: dict[str, dict[str, Any]] = {}
        after: str | None = None
        max_pages = 16

        try:
            for _ in range(max_pages):
                params = {
                    "instId": clean_symbol,
                    "bar": bar,
                    "limit": "100",
                }
                if after is not None:
                    params["after"] = after

                response = requests.get(
                    "https://www.okx.com/api/v5/market/history-candles",
                    params=params,
                    timeout=6,
                )
                response.raise_for_status()
                payload = response.json()
                rows = (
                    payload.get("data", [])
                    if payload.get("code") == "0"
                    else []
                )

                if not rows:
                    break

                oldest_page_timestamp: str | None = None
                for row in rows:
                    if len(row) < 9:
                        continue
                    timestamp = str(row[0])
                    oldest_page_timestamp = timestamp
                    if str(row[8]) != "1":
                        continue
                    collected[timestamp] = {
                        "timestamp": timestamp,
                        "high": float(row[2]),
                        "low": float(row[3]),
                    }

                if oldest_signal is not None and oldest_page_timestamp is not None:
                    if str(oldest_page_timestamp) <= str(oldest_signal):
                        break

                next_after = oldest_page_timestamp
                if next_after is None or next_after == after:
                    break
                after = next_after

                if len(rows) < 100:
                    break

            completed = [collected[key] for key in sorted(collected)]
            self._history_cache[cache_key] = completed
            return completed
        except Exception:
            self._history_cache[cache_key] = []
            return []

    def _process_one_market_bar(
        self,
        *,
        symbol: str,
        timeframe: str,
        high: float,
        low: float,
        timestamp: str | None,
    ) -> list[Any]:
        processed: list[Any] = []

        for outcome in list(self.tracker.outcomes.values()):
            if outcome.resolved:
                continue
            if str(outcome.symbol) != str(symbol):
                continue
            if str(outcome.timeframe) != str(timeframe):
                continue

            metadata = outcome.metadata or {}

            if timestamp is not None:
                signal_timestamp = metadata.get("candle_timestamp")
                if signal_timestamp is not None and str(timestamp) <= str(signal_timestamp):
                    continue

                last_processed = metadata.get("last_processed_timestamp")
                if last_processed == str(timestamp):
                    continue

            result = self.tracker.process_bar(
                signal_id=outcome.signal_id,
                high=float(high),
                low=float(low),
                timestamp=timestamp,
            )

            if timestamp is not None:
                metadata["last_processed_timestamp"] = str(timestamp)
                outcome.metadata = metadata
                self.tracker.save()

            if result is not None and result.resolved:
                processed.append(result)

        return processed

    def process_market_bar(
        self,
        *,
        symbol: str,
        timeframe: str,
        high: float,
        low: float,
        timestamp: str | None = None,
    ) -> list[Any]:
        storage_path = str(
            getattr(self.tracker, "storage_path", "shadow_outcomes.json")
        )
        with self._lock_for(storage_path):
            self._sync_storage_context()

            if not self._pending_for_market(
                symbol=symbol,
                timeframe=timeframe,
            ):
                return []

            history = self._fetch_completed_history(
                symbol=symbol,
                timeframe=timeframe,
                current_timestamp=str(timestamp) if timestamp is not None else "",
            )

            processed: list[Any] = []
            for bar in history:
                processed.extend(
                    self._process_one_market_bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        high=bar["high"],
                        low=bar["low"],
                        timestamp=bar["timestamp"],
                    )
                )
            return processed

    def process_market_bars(
        self,
        *,
        symbol: str,
        timeframe: str,
        bars,
    ) -> list[Any]:
        storage_path = str(
            getattr(self.tracker, "storage_path", "shadow_outcomes.json")
        )
        with self._lock_for(storage_path):
            self._sync_storage_context()
            processed: list[Any] = []

            for bar in bars:
                if isinstance(bar, dict):
                    timestamp = bar.get("timestamp")
                    high = bar.get("high")
                    low = bar.get("low")
                else:
                    timestamp, high, low = bar

                if timestamp is None or high is None or low is None:
                    continue

                processed.extend(
                    self._process_one_market_bar(
                        symbol=symbol,
                        timeframe=timeframe,
                        high=float(high),
                        low=float(low),
                        timestamp=str(timestamp),
                    )
                )

            return processed

    def register_if_accepted(
        self,
        *,
        signal: dict[str, Any],
        strategy_type: str,
        result: Any,
    ):
        storage_path = str(
            getattr(self.tracker, "storage_path", "shadow_outcomes.json")
        )
        with self._lock_for(storage_path):
            self._sync_storage_context()

            if not self.is_shadow_accepted(result):
                return None

            signal_id = self.build_signal_id(
                signal=signal,
                strategy_type=strategy_type,
            )

            metadata = {
                "source": "scanner_shadow",
                "mode": "SHADOW",
                "candle_timestamp": signal.get("candle_timestamp"),
                "audit_event_id": self._read_value(
                    result,
                    "audit_event_id",
                    None,
                ),
            }

            direction = signal.get(
                "direction",
                signal.get("side", "long"),
            )

            return self.tracker.register(
                signal_id=signal_id,
                symbol=str(signal["symbol"]),
                timeframe=str(signal.get("timeframe", "1h")),
                strategy=str(strategy_type),
                entry=float(signal["price"]),
                stop_loss=float(signal["stop_loss"]),
                direction=str(direction),
                target_1=(
                    float(signal["target1"])
                    if signal.get("target1") is not None
                    else None
                ),
                target_2=(
                    float(signal["target2"])
                    if signal.get("target2") is not None
                    else None
                ),
                target_3=(
                    float(signal["target3"])
                    if signal.get("target3") is not None
                    else None
                ),
                target_4=(
                    float(signal["target4"])
                    if signal.get("target4") is not None
                    else None
                ),
                macro_target=(
                    float(signal["macro_target"])
                    if signal.get("macro_target") is not None
                    else None
                ),
                metadata=metadata,
            )
