from enum import Enum


class ExecutionMode(str, Enum):
    LEGACY = "legacy"
    SHADOW = "shadow"
    LIVE = "live"
