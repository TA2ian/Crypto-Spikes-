# Risk & Strategy Eligibility Engine V2

## Purpose

Sprint 006 determines whether an already analyzed setup is eligible
for a trading decision.

It does not execute trades.

---

## Pipeline

```text
Evidence
   ↓
Confluence
   ↓
Decision
   ↓
Risk & Eligibility
   ↓
EligibilityResult
   ↓
TradeCase
