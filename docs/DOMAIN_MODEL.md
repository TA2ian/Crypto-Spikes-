# Domain Model

## AssetProfile

Represents one market asset.

Fields:

- symbol
- exchange
- trend
- market regime
- structural bias

---

## MarketContext

Represents global market conditions.

- BTC Trend
- BTC Dominance
- USDT Dominance
- Fear & Greed
- Volatility

---

## Evidence

Represents one piece of trading evidence.

Fields:

- type
- direction
- strength
- timeframe
- reliability
- freshness
- source

---

## Decision

Represents the final trading decision.

Fields:

- action
- confidence
- risk
- evidence
- explanation

---

## TradeCase

Represents one trade lifecycle.

States:

Waiting

↓

Ready

↓

Entry

↓

Active

↓

Partial TP

↓

Trailing

↓

Closed
