from __future__ import annotations

from .models import LockedTargets


def lock_targets(
    *,
    entry: float,
    stop_loss: float,
    target_1: float | None = None,
    target_2: float | None = None,
    target_3: float | None = None,
    target_4: float | None = None,
) -> LockedTargets:

    if entry <= 0:
        raise ValueError(
            "Entry must be positive."
        )

    if stop_loss <= 0:
        raise ValueError(
            "Stop loss must be positive."
        )

    return LockedTargets(
        entry=entry,
        stop_loss=stop_loss,
        target_1=target_1,
        target_2=target_2,
        target_3=target_3,
        target_4=target_4,
    )
