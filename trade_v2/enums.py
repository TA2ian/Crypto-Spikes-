from enum import Enum


class TradeStatus(str, Enum):
    CANDIDATE = "candidate"
    READY = "ready"
    ENTERED = "entered"
    ACTIVE = "active"
    PARTIAL_TP = "partial_tp"
    TRAILING = "trailing"
    CLOSED = "closed"
    INVALIDATED = "invalidated"


class EntryType(str, Enum):
    INITIAL = "initial"
    RETEST = "retest"
    REENTRY = "reentry"


class ExitReason(str, Enum):
    TARGET_1 = "target_1"
    TARGET_2 = "target_2"
    TARGET_3 = "target_3"
    TARGET_4 = "target_4"
    STOP_LOSS = "stop_loss"
    INVALIDATION = "invalidation"
    MANUAL = "manual"
    SYSTEM = "system"


class Direction(str, Enum):
    LONG = "long"
    SHORT = "short"
