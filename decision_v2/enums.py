from enum import Enum


class DecisionAction(str, Enum):
    ACCEPT = "accept"
    REJECT = "reject"
    WAIT = "wait"


class DecisionDirection(str, Enum):
    LONG = "long"
    SHORT = "short"
    NEUTRAL = "neutral"


class EntryType(str, Enum):
    INITIAL = "initial"
    RETEST = "retest"
    REENTRY = "reentry"


class DecisionGrade(str, Enum):
    A_PLUS = "A+"
    A = "A"
    B = "B"
    C = "C"
    INVALID = "invalid"


class GateStatus(str, Enum):
    PASS = "pass"
    FAIL = "fail"
    WARNING = "warning"


class RejectionReason(str, Enum):
    LOW_CONFLUENCE = "low_confluence"
    HTF_CONFLICT = "htf_conflict"
    RISK_GATE_FAILED = "risk_gate_failed"
    BEARISH_CONFLICT = "bearish_conflict"
    INVALID_CONTEXT = "invalid_context"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    DUPLICATE_ENTRY = "duplicate_entry"
    STRATEGY_NOT_ELIGIBLE = "strategy_not_eligible"
