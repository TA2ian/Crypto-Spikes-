# Decision Engine V2

## Purpose

The Decision Engine converts normalized market evidence and confluence
into a controlled, explainable decision.

It does not execute trades.

---

## Pipeline

```text
AssetProfile
      ↓
MarketContext
      ↓
Evidence
      ↓
Confluence
      ↓
MarketHypothesis
      ↓
DecisionEngine
      ↓
DecisionResult
      ↓
TradeCase
