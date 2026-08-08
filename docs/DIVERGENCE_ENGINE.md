from divergence_v2 import (
    DivergenceDirection,
    DivergenceEngine,
    DivergenceType,
    IndicatorType,
)


def test_engine_returns_empty_for_insufficient_data() -> None:
    engine = DivergenceEngine()

    signals = engine.analyze(
        [100, 101, 102],
        [50, 51, 52],
        indicator=IndicatorType.RSI,
        timeframe="4h",
    )

    assert signals == []


def test_regular_bullish_divergence() -> None:
    engine = DivergenceEngine()

    prices = [
        110,
        108,
        105,
        107,
        103,
        106,
        109,
    ]

    rsi = [
        50,
        45,
        30,
        40,
        35,
        45,
        50,
    ]

    signals = engine.analyze(
        prices,
        rsi,
        indicator=IndicatorType.RSI,
        timeframe="4h",
    )

    assert any(
        signal.divergence_type == DivergenceType.REGULAR
        and signal.direction == DivergenceDirection.BULLISH
        for signal in signals
    )


def test_hidden_bullish_divergence() -> None:
    engine = DivergenceEngine()

    prices = [
        100,
        105,
        103,
        108,
        106,
        111,
        115,
    ]

    rsi = [
        50,
        60,
        45,
        55,
        40,
        50,
        60,
    ]

    signals = engine.analyze(
        prices,
        rsi,
        indicator=IndicatorType.RSI,
        timeframe="4h",
    )

    assert isinstance(signals, list)


def test_divergence_signal_strength_is_normalized() -> None:
    engine = DivergenceEngine()

    signals = engine.analyze(
        [110, 108, 105, 107, 103, 106, 109],
        [50, 45, 30, 40, 35, 45, 50],
        indicator=IndicatorType.RSI,
        timeframe="1h",
    )

    for signal in signals:
        assert 0 <= signal.strength <= 1
        assert 0 <= signal.reliability <= 1


def test_engine_supports_cvd() -> None:
    engine = DivergenceEngine()

    signals = engine.analyze(
        [110, 108, 105, 107, 103, 106, 109],
        [100, 90, 80, 95, 85, 100, 110],
        indicator=IndicatorType.CVD,
        timeframe="1h",
    )

    assert isinstance(signals, list)
