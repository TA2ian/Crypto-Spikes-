"""
V2 Divergence Engine.

Supports:

- Regular divergence
- Hidden divergence
- Exaggerated divergence
- Triple divergence
"""

from .detector import (
    detect_exaggerated,
    detect_hidden,
    detect_regular,
    detect_triple,
)

from .engine import DivergenceEngine

from .enums import (
    DivergenceDirection,
    DivergenceType,
    IndicatorType,
    PivotType,
)

from .models import (
    DivergenceSignal,
    Pivot,
)

__all__ = [
    "DivergenceEngine",
    "DivergenceDirection",
    "DivergenceSignal",
    "DivergenceType",
    "IndicatorType",
    "Pivot",
    "PivotType",
    "detect_exaggerated",
    "detect_hidden",
    "detect_regular",
    "detect_triple",
]
