from enum import Enum


class EligibilityStatus(str, Enum):
    ELIGIBLE = "eligible"
    BLOCKED = "blocked"
    WARNING = "warning"


class RiskLevel(str, Enum):
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    EXTREME = "extreme"


class StrategyType(str, Enum):
    WYCKOFF_SMC = "wyckoff_smc_accumulation"
    CVD_SQUEEZE = "cvd_squeeze_breakout"
    TREND_FOLLOWING = "precision_trend_following"
    MEAN_REVERSION = "mean_reversion"
    CHART_PATTERN = "verified_chart_pattern"
    FVG_SCALP = "fvg_scalp"
    ULTIMATE_A_PLUS = "ultimate_master_a_plus"
    CAPITULATION = "capitulation_bottom"


class RiskBlockReason(str, Enum):
    HALAL_INELIGIBLE = "halal_ineligible"
    ASSET_NOT_SUPPORTED = "asset_not_supported"
    HTF_CONFLICT = "htf_conflict"
    MACRO_CONFLICT = "macro_conflict"
    VOLATILITY_TOO_HIGH = "volatility_too_high"
    VOLATILITY_TOO_LOW = "volatility_too_low"
    RISK_BUDGET_EXCEEDED = "risk_budget_exceeded"
    INVALID_STOP = "invalid_stop"
    INVALID_TARGET = "invalid_target"
    INSUFFICIENT_RR = "insufficient_rr"
    STRATEGY_NOT_ELIGIBLE = "strategy_not_eligible"
    ACTIVE_TRADE_CONFLICT = "active_trade_conflict"
    INVALID_CONTEXT = "invalid_context"
