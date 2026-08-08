# V2 Integration — Sprint 008

Sprint 008 introduces the integration boundary between the V2 engines.

## Pipeline

Market Evidence
→ Decision V2
→ Risk / Strategy Eligibility
→ Trade Lifecycle

## Execution Modes

### LEGACY

Reserved for the existing scanner behavior.

### SHADOW

Runs V2 analysis and records the result,
but does not create a trade.

### LIVE

Permits TradeState creation only after:

- Decision is accepted
- Risk eligibility passes

Sprint 008 does not submit exchange orders.

## Safety Boundaries

- `scanner.py` is not replaced by the V2 pipeline.
- Risk failure always blocks trade creation.
- Decision rejection always blocks trade creation.
- Audit events record the decision, eligibility,
  and whether a trade was created.
- Historical replay passes only prior events to the callback.
- Future events are never exposed to the replay callback.

## Target Integrity

Trade creation uses the locked target model from Sprint 007.

Retest and Re-entry handling remains inside `trade_v2`
and does not recalculate structural targets.

## Current Limitations

The following are intentionally deferred:

- Real scanner adapter
- Persistent audit storage
- Exchange execution adapter
- Full historical outcome simulator
- End-to-end regression against legacy behavior

## Next Stage

Sprint 008-E will connect the existing scanner to the
V2 pipeline in Shadow Mode and compare V2 decisions
against the current production behavior without
submitting exchange orders.
