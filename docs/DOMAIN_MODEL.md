# Domain Model — V2

## Purpose

The domain model defines the canonical language shared by the V2
market intelligence, decision and trade lifecycle engines.

The models do not fetch market data, execute trades, send alerts,
or calculate technical indicators.

They represent domain state.

---

# 1. AssetProfile

Represents the identity and high-level state of an asset.

### Responsibilities

- Asset identity
- Exchange
- Market type
- Watchlist state
- Halal classification
- Macro trend
- Structural bias
- Market regime
- Volatility state
- Liquidity state

### Explicitly excluded

Raw technical indicators such as:

- RSI
- MACD
- EMA
- ATR
- CVD

These belong to the feature/evidence layers.

---

# 2. MarketContext

Represents the global market environment at a specific point in time.

Includes:

- BTC trend
- BTC dominance
- USDT dominance
- Fear & Greed
- Market volatility
- Macro trend
- Risk regime
- Trading session
- Market breadth

The purpose is to prevent individual strategies from reconstructing
the global market context independently.

---

# 3. Evidence

Evidence represents an observable or derived market fact.

Evidence is not a trading decision.

### Core fields

- ID
- Type
- Direction
- Strength
- Timeframe
- Source
- Reliability
- Freshness
- Timestamp
- Metadata

### Evidence Types

- Trend
- Structure
- Liquidity Sweep
- Order Block
- FVG
- Divergence
- Volume
- Momentum
- Volatility
- Support
- Resistance
- Pattern
- Dominance
- Sentiment

---

# 4. Divergence Evidence

Divergence is represented as Evidence.

Supported divergence types:

- Regular
- Hidden
- Exaggerated
- Triple

Supported directions:

- Bullish
- Bearish

Example:

```text
type       = DIVERGENCE
subtype    = HIDDEN
direction  = BULLISH
timeframe  = 4h
strength   = 0.90
reliability = 0.95
freshness  = 0.90
