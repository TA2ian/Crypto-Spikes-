from risk_v2 import atr_percent


def test_atr_percent() -> None:
    assert atr_percent(
        atr=5.0,
        price=100.0,
    ) == 5.0
