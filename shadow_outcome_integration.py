from __future__ import annotations

from typing import Any

import requests

from shadow_outcomes import ShadowOutcomeTracker


class ShadowOutcomeIntegration:
    """
    Adapter between Scanner Shadow results and ShadowOutcomeTracker.

    Observation-only:
    this layer never opens, modifies, or closes real trades.

    Historical reconciliation is intentionally kept here so the legacy
    scanner can continue calling process_market_bar() unchanged while
    pending V2 outcomes are checked against completed candles that may
    have occurred between scanner runs.
    """

    _OKX_BAR_MAP = {
        "15m": "15m",
        "1h": "1H",
        "4h": "4H",
        "1d": "1D",
        "3d": "3D",
        "1w": "1W",
    }

    def __init__(
        self,
        tracker: ShadowOutcomeTracker | None = None,
    ) -> None:
        self.tracker = (
            tracker
            or ShadowOutcomeTracker(
                storage_path="shadow_outcomes.json"
            )
        )
        self._loaded_storage_path = getattr(
            self.tracker,
            "storage_path",
            None,
        )
        self._history_cache: dict[tuple[str, str, str], list[dict[str, Any]]] = {}

    @staticmethod
    def build_signal_id(
        signal: dict[str, Any],
        strategy_type: str,
    ) -> str:
        symbol = str(signal.get("symbol", "UNKNOWN"))
        timeframe = str(signal.get("timeframe", "UNKNOWN"))
        entry = float(signal.get("price", 0.0))
        return f"{symbol}-{timeframe}-{strategy_type}-{entry:.8f}"

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
    def is_shadow_accepted(
        cls,
        result: Any,
    ) -> bool:
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
        if current_path is None or current_path == self._loaded_storage_path:
            return

        self.tracker.outcomes = {}
        self._loaded_storage_path = current_path

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

    def _fetch_completed_history(
        self,
        *,
        symbol: str,
        timeframe: str,
        current_timestamp: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch recent completed OKX candles for reconciliation.

        OKX explicitly exposes candle confirmation state; only candles
        with confirm=1 are admitted to the shadow outcome engine.
        The scanner's existing current-bar call remains the trigger,
        so no scanner-side API integration is required.
        """
        cache_key = (str(symbol), str(timeframe), str(current_timestamp))
        if cache_key in self._history_cache:
            return self._history_cache[cache_key]

        bar = self._OKX_BAR_MAP.get(str(timeframe))
        if bar is None:
            return []

        clean_symbol = str(symbol).replace("/", "-").upper()
        if not clean_symbol.endswith("-USDT"):
            clean_symbol = f"{clean_symbol}-USDT"

        try:
            response = requests.get(
                "https://www.okx.com/api/v5/market/candles",
                params={
                    "instId": clean_symbol,
                    "bar": bar,
                    "limit": "100",
                },
                timeout=6,
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("data", []) if payload.get("code") == "0" else []

            completed: list[dict[str, Any]] = []
            for row in reversed(rows):
                if len(row) < 9 or str(row[8]) != "1":
                    continue
                completed.append(
                    {
                        "timestamp": str(row[0]),
                        "high": float(row[2]),
                        "low": float(row[3]),
                    }
                )

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

            if result is not None:
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
        """
        Reconcile pending outcomes against completed history, then
        process the supplied completed/current market bar.

        The history pass is observation-only and respects the signal
        candle boundary plus per-candle deduplication.
        """
        self._sync_storage_context()
        processed: list[Any] = []

        if self._pending_for_market(symbol=symbol, timeframe=timeframe):
            history = self._fetch_completed_history(
                symbol=symbol,
                timeframe=timeframe,
                current_timestamp=str(timestamp) if timestamp is not None else "",
            )
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

        processed.extend(
            self._process_one_market_bar(
                symbol=symbol,
                timeframe=timeframe,
                high=high,
                low=low,
                timestamp=timestamp,
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
        """
        Reconcile pending Shadow Outcomes against supplied historical
        completed candles. Bars at or before the signal candle are ignored.
        """
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
            "audit_event_id": self._read_value(result, "audit_event_id", None),
        }

        return self.tracker.register(
            signal_id=signal_id,
            symbol=str(signal["symbol"]),
            timeframe=str(signal.get("timeframe", "1h")),
            strategy=str(strategy_type),
            entry=float(signal["price"]),
            stop_loss=float(signal["stop_loss"]),
            target_1=float(signal["target1"]) if signal.get("target1") is not None else None,
            target_2=float(signal["target2"]) if signal.get("target2") is not None else None,
            target_3=float(signal["target3"]) if signal.get("target3") is not None else None,
            target_4=float(signal["target4"]) if signal.get("target4") is not None else None,
            macro_target=float(signal["macro_target"]) if signal.get("macro_target") is not None else None,
            metadata=metadata,
        )
