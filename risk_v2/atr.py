def atr_percent(
    *,
    atr: float,
    price: float,
) -> float:
    """
    Return ATR as percentage of current price.
    """

    if price <= 0:
        raise ValueError(
            "price must be positive"
        )

    if atr < 0:
        raise ValueError(
            "atr cannot be negative"
        )

    return (
        atr / price
    ) * 100.0
