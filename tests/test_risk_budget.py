from risk_v2 import evaluate_risk_budget


def test_risk_budget_passes() -> None:
    result = evaluate_risk_budget(
        account_equity=10_000.0,
        risk_percent=1.0,
        maximum_risk_percent=2.0,
    )

    assert result.allowed is True
    assert result.risk_amount == 100.0


def test_risk_budget_blocks_excessive_risk() -> None:
    result = evaluate_risk_budget(
        account_equity=10_000.0,
        risk_percent=3.0,
        maximum_risk_percent=2.0,
    )

    assert result.allowed is False
