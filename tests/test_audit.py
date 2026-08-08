from integration_v2 import (
    AuditEvent,
    AuditTrail,
    ExecutionMode,
)


def test_audit_trail_records_and_filters():

    trail = AuditTrail()

    trail.record(
        AuditEvent(
            event_type="x",
            symbol="BTCUSDT",
            mode=ExecutionMode.SHADOW,
        )
    )

    trail.record(
        AuditEvent(
            event_type="x",
            symbol="ETHUSDT",
            mode=ExecutionMode.SHADOW,
        )
    )

    assert len(
        trail.events()
    ) == 2

    assert len(
        trail.for_symbol("btcusdt")
    ) == 1
