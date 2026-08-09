import pandas as pd

from scanner_shadow import (
    HTF_BY_SIGNAL_TIMEFRAME,
    _higher_timeframe,
    _trend_bullish_from_frame,
)


def _frame(closes: list[float]) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "close": closes,
            "open": closes,
            "high": closes,
            "low": closes,
            "volume": [1.0] * len(closes),
        }
    )


def test_signal_timeframe_maps_to_independent_htf():
    assert HTF_BY_SIGNAL_TIMEFRAME == {
        "15m": "1h",
        "1h": "4h",
        "4h": "1d",
        "1d": "3d",
        "3d": "1w",
        "1w": None,
    }
    assert _higher_timeframe("1h") == "4h"
    assert _higher_timeframe("4H") == "1d"
    assert _higher_timeframe("1d") == "3d"


def test_htf_bullish_rule_uses_closed_candle():
    closes = [100.0 + i for i in range(25)]
    frame = _frame(closes)

    assert _trend_bullish_from_frame(frame) is True


def test_htf_context_is_conservative_when_data_is_insufficient():
    frame = _frame([100.0] * 10)

    assert _trend_bullish_from_frame(frame) is False
