# V2 Stabilization Pass

## Scope

This pass stabilizes the V2 foundation after Sprints 001–005.

### Changes

- Improved divergence pivot handling:
  - Default engine pivot window is now 1/1 for the foundation detector.
  - Divergence comparisons scan compatible historical pivot pairs instead of assuming the last two pivots are the only valid pair.
  - Triple divergence evaluates consecutive same-type pivot groups.
- Fixed floating-point test precision using `pytest.approx`.
- Added a Decision V2 → canonical Domain Decision adapter.
- Added adapter coverage to the test suite.
- Legacy `scanner.py` and existing trade execution code were not modified.

## Verification

```text
37 passed
