from __future__ import annotations


def risk_per_unit(
    *,
    entry: float,
    stop: float,
) -> float:

    if entry <= 0 or stop <= 0:
        raise ValueError(
            "entry and stop must be positive"
        )

    return abs(
        entry - stop
    )


def reward_per_unit(
    *,
    entry: float,
    target: float,
) -> float:

    if entry <= 0 or target <= 0:
        raise ValueError(
            "entry and target must be positive"
        )

    return abs(
        target - entry
    )


def risk_reward(
    *,
    entry: float,
    stop: float,
    target: float,
) -> float:

    risk = risk_per_unit(
        entry=entry,
        stop=stop,
    )

    if risk <= 0:
        raise ValueError(
            "risk must be greater than zero"
        )

    reward = reward_per_unit(
        entry=entry,
        target=target,
    )

    return reward / risk
