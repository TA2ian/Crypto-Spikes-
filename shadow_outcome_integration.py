from __future__ import annotations

from typing import Any

from shadow_outcomes import ShadowOutcomeTracker


class ShadowOutcomeIntegration:
    """
    Adapter between Scanner Shadow results and the
    ShadowOutcomeTracker.

    This adapter is observation-only.
    It never opens, modifies, or closes real trades.
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

    @staticmethod
    def build_signal_id(
        signal: dict[str, Any],
        strategy_type: str,
    ) -> str:
        symbol = str(
            signal.get("symbol", "UNKNOWN")
        )

        timeframe = str(
            signal.get("timeframe", "UNKNOWN")
        )

        entry = float(
            signal.get("price", 0.0)
        )

        return (
            f"{symbol}-"
            f"{timeframe}-"
            f"{strategy_type}-"
            f"{entry:.8f}"
        )

    @staticmethod
    def is_shadow_accepted(
        result: Any,
    ) -> bool:
        """
        Accept only an actual V2 shadow decision.

        A missing result is never treated as acceptance.
        """

        if result is None:
            return False

        status = getattr(
            result,
            "status",
            None,
        )

        if isinstance(status, str):
            normalized = status.lower()

            if normalized in {
                "shadow_error",
                "error",
                "reject",
                "rejected",
            }:
                return False

        action = getattr(
            result,
            "action",
            None,
        )

        if isinstance(action, str):
            normalized = action.lower()

            if normalized in {
                "reject",
                "rejected",
                "wait",
            }:
                return False

            if normalized in {
                "accept",
                "accepted",
            }:
                return True

        decision = getattr(
            result,
            "decision",
            None,
        )

        if isinstance(decision, str):
            normalized = decision.lower()

            if normalized in {
                "reject",
                "rejected",
                "wait",
            }:
                return False

            if normalized in {
                "accept",
                "accepted",
            }:
                return True

        # If the result exists but its API does not expose
        # an explicit acceptance field, do not silently
        # register it as an executable signal.
        return False

    def register_if_accepted(
        self,
        *,
        signal: dict[str, Any],
        strategy_type: str,
        result: Any,
    ):
        """
        Register a V2 signal only when the V2 result
        explicitly says ACCEPT.

        Returns:
            ShadowOutcome | None
        """

        if not self.is_shadow_accepted(
            result
        ):
            return None

        signal_id = self.build_signal_id(
            signal=signal,
            strategy_type=strategy_type,
        )

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
            metadata={
                "source": "scanner_shadow",
                "mode": "SHADOW",
                "audit_event_id": getattr(
                    result,
                    "audit_event_id",
                    None,
                ),
            },
        )
