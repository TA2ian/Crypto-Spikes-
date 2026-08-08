from __future__ import annotations

from .models import DecisionGate


def build_explanation(
    *,
    action: str,
    direction: str,
    grade: str,
    confidence: float,
    gates: tuple[DecisionGate, ...],
) -> str:

    passed = [
        gate.name
        for gate in gates
        if gate.status.value == "pass"
    ]

    failed = [
        gate.name
        for gate in gates
        if gate.status.value == "fail"
    ]

    parts = [
        f"Action={action}",
        f"Direction={direction}",
        f"Grade={grade}",
        f"Confidence={confidence:.3f}",
    ]

    if passed:
        parts.append(
            "Passed gates: " + ", ".join(passed)
        )

    if failed:
        parts.append(
            "Failed gates: " + ", ".join(failed)
        )

    return " | ".join(parts)
