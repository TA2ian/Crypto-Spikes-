from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DecisionThresholds:
    minimum_confluence: float = 0.55
    strong_confluence: float = 0.70
    a_plus_confluence: float = 0.82

    minimum_evidence: int = 3

    minimum_reliability: float = 0.60

    maximum_conflict_ratio: float = 0.40

    a_plus_min_supporting_evidence: int = 5


DEFAULT_THRESHOLDS = DecisionThresholds()
