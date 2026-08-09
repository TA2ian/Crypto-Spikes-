from __future__ import annotations

from typing import Any

from shadow_outcomes import ShadowOutcomeTracker


class ShadowOutcomeIntegration:
    """
    Adapter between Scanner Shadow results and
    ShadowOutcomeTracker.

    Observation-only:
    this layer never opens, modifies, or closes real trades.
    """

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

        # Track the storage path that was actually loaded
        # during tracker initialization.
        #
        # Tests may replace tracker.storage_path after
        # initialization. When that happens, the old in-memory
        # outcomes must not leak into the new storage context.
        self._loaded_storage_path = getattr(
            self.tracker,
            "storage_path",
            None,
        )

    @staticmethod
    def build_signal_id(
        signal: dict[str, Any],
        strategy_type: str,
    ) -> str:
        symbol = str(
            signal.get(
                "symbol",
                "UNKNOWN",
            )
        )

        timeframe = str(
            signal.get(
                "timeframe",
                "UNKNOWN",
            )
        )

        entry = float(
            signal.get(
                "price",
                0.0,
            )
        )

        return (
            f"{symbol}-"
            f"{timeframe}-"
            f"{strategy_type}-"
            f"{entry:.8f}"
        )

    @staticmethod
    def _read_value(
        obj: Any,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Read a value from either an object or a dictionary.
        """
        if obj is None:
            return default

        if isinstance(obj, dict):
            return obj.get(
                key,
                default,
            )

        return getattr(
            obj,
            key,
            default,
        )

    @classmethod
    def is_shadow_accepted(
        cls,
        result: Any,
    ) -> bool:
        """
        Return True only when the V2 result explicitly
        reports an accepted decision.

        Priority:
            1. result.decision.accepted
            2. result.decision as a string
            3. result.action as a fallback

        A missing result is NEVER accepted.
        """

        if result is None:
            return False

        # --------------------------------------------------
        # Primary V2 API:
        # result.decision.accepted
        # --------------------------------------------------
        decision = cls._read_value(
            result,
            "decision",
            None,
        )

        if decision is not None:
            accepted = cls._read_value(
                decision,
                "accepted",
                None,
            )

            if isinstance(
                accepted,
                bool,
            ):
                return accepted

            if isinstance(
                accepted,
                str,
            ):
                normalized = (
                    accepted
                    .strip()
                    .lower()
                )

                if normalized in {
                    "true",
                    "yes",
                    "accept",
                    "accepted",
                }:
                    return True

                if normalized in {
                    "false",
                    "no",
                    "reject",
                    "rejected",
                    "wait",
                }:
                    return False

            # --------------------------------------------------
            # Backward compatibility:
            # decision itself may be a string.
            # --------------------------------------------------
            if isinstance(
                decision,
                str,
            ):
                normalized = (
                    decision
                    .strip()
                    .lower()
                )

                if normalized in {
                    "accept",
                    "accepted",
                }:
                    return True

                if normalized in {
                    "reject",
                    "rejected",
                    "wait",
                }:
                    return False

            # --------------------------------------------------
            # If a decision object exists but doesn't explicitly
            # expose acceptance, do NOT infer acceptance from
            # another unrelated field.
            # --------------------------------------------------
            return False

        # --------------------------------------------------
        # Fallback only when no decision exists at all.
        # --------------------------------------------------
        action = cls._read_value(
            result,
            "action",
            None,
        )

        if isinstance(
            action,
            str,
        ):
            normalized = (
                action
                .strip()
                .lower()
            )

            if normalized in {
                "accept",
                "accepted",
            }:
                return True

            if normalized in {
                "reject",
                "rejected",
                "wait",
            }:
                return False

        return False

    def _sync_storage_context(self) -> None:
        """
        Keep in-memory outcomes aligned with the currently
        configured storage path when the tracker exposes one.

        Lightweight test doubles such as FakeTracker may not
        provide storage_path; in that case no synchronization
        is required.
        """

        current_path = getattr(
            self.tracker,
            "storage_path",
            None,
        )

        if current_path is None:
            return

        if current_path == self._loaded_storage_path:
            return

        self.tracker.outcomes = {}

        self._loaded_storage_path = current_path

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
        Process one completed market candle against existing
        pending shadow outcomes.

        Observation-only:
        this method never creates, modifies, or closes real trades.

        The current candle is processed at most once per outcome.
        Newly registered signals are therefore not evaluated against
        the candle that created them.
        """
        self._sync_storage_context()

        processed: list[Any] = []

        for outcome in list(
            self.tracker.outcomes.values()
        ):
            if outcome.resolved:
                continue

            if str(outcome.symbol) != str(symbol):
                continue

            if str(outcome.timeframe) != str(timeframe):
                continue

            metadata = outcome.metadata or {}

            if timestamp is not None:
                signal_timestamp = metadata.get(
                    "candle_timestamp"
                )

                # Never evaluate the candle that created the signal,
                # or any candle older than that signal candle.
                if (
                    signal_timestamp is not None
                    and str(timestamp) <= str(signal_timestamp)
                ):
                    continue

                # A candle must be processed at most once.
                last_processed = metadata.get(
                    "last_processed_timestamp"
                )

                if last_processed == str(timestamp):
                    continue

            result = self.tracker.process_bar(
                signal_id=outcome.signal_id,
                high=float(high),
                low=float(low),
                timestamp=timestamp,
            )

            # Record the candle even when the outcome remains PENDING.
            # This prevents the same candle from being processed again.
            if timestamp is not None:
                metadata["last_processed_timestamp"] = str(timestamp)
                outcome.metadata = metadata
                self.tracker.save()

            if result is not None:
                processed.append(result)

        return processed

    def register_if_accepted(
        self,
        *,
        signal: dict[str, Any],
        strategy_type: str,
        result: Any,
    ):
        """
        Register an outcome only for an explicitly
        accepted V2 shadow signal.

        Returns:
            ShadowOutcome | None

        This is observation-only.
        """

        self._sync_storage_context()

        if not self.is_shadow_accepted(
            result
        ):
            return None

        signal_id = self.build_signal_id(
            signal=signal,
            strategy_type=strategy_type,
        )

        metadata = {
            "source": "scanner_shadow",
            "mode": "SHADOW",
            "candle_timestamp": signal.get(
                "candle_timestamp"
            ),
            "audit_event_id": self._read_value(
                result,
                "audit_event_id",
                None,
            ),
        }

        return self.tracker.register(
            signal_id=signal_id,
            symbol=str(
                signal["symbol"]
            ),
            timeframe=str(
                signal.get(
                    "timeframe",
                    "1h",
                )
            ),
            strategy=str(
                strategy_type
            ),
            entry=float(
                signal["price"]
            ),
            stop_loss=float(
                signal["stop_loss"]
            ),
            target_1=(
                float(
                    signal["target1"]
                )
                if signal.get(
                    "target1"
                ) is not None
                else None
            ),
            target_2=(
                float(
                    signal["target2"]
                )
                if signal.get(
                    "target2"
                ) is not None
                else None
            ),
            target_3=(
                float(
                    signal["target3"]
                )
                if signal.get(
                    "target3"
                ) is not None
                else None
            ),
            target_4=(
                float(
                    signal["target4"]
                )
                if signal.get(
                    "target4"
                ) is not None
                else None
            ),
            macro_target=(
                float(
                    signal["macro_target"]
                )
                if signal.get(
                    "macro_target"
                ) is not None
                else None
            ),
            metadata=metadata,
        )
