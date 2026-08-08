import pytest

from risk_v2 import risk_reward


def test_risk_reward() -> None:
    result = risk_reward(
        entry=100.0,
        stop=95.0,
        target=110.0,
    )

    assert result == pytest.approx(2.0)


def test_invalid_zero_risk() -> None:
    with pytest.raises(ValueError):
        risk_reward(
            entry=100.0,
            stop=100.0,
            target=110.0,
        )
