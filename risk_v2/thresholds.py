from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RiskThresholds:
    minimum_rr: float = 1.5

    maximum_risk_percent: float = 2.0

    minimum_atr_percent: float = 0.20
    maximum_atr_percent: float = 15.0

    maximum_risk_score: float = 0.75

    minimum_strategy_score: float = 0.60

    maximum_active_positions: int = 5


DEFAULT_RISK_THRESHOLDS = RiskThresholds()
