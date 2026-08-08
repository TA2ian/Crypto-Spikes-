from datetime import (
    datetime,
    timedelta,
    timezone,
)

from integration_v2 import (
    HistoricalReplay,
    ReplayEvent,
)


def test_replay_does_not_expose_future_events():

    timestamp = datetime(
        2026,
        1,
        1,
        tzinfo=timezone.utc,
    )

    events = [
        ReplayEvent(
            timestamp
            + timedelta(minutes=i),
            i,
        )
        for i in range(3)
    ]

    seen = []

    def callback(
        event,
        history,
    ):

        seen.append(
            (
                event.payload,
                [
                    item.payload
                    for item in history
                ],
            )
        )

        return event.payload

    result = HistoricalReplay().run(
        events,
        callback,
    )

    assert result.processed == 3

    assert seen == [
        (0, []),
        (1, [0]),
        (2, [0, 1]),
    ]
