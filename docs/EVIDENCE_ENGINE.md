# Evidence & Confluence Engine V2

## Purpose

The Evidence Engine converts independent market observations into
normalized, traceable evidence.

The Confluence Engine evaluates how strongly those pieces of evidence
agree with one another.

The system does not execute trades at this layer.

---

## Architecture

```text
Market Data
     ↓
Feature Extraction
     ↓
Individual Engines
     │
     ├── Trend
     ├── Structure
     ├── SMC
     ├── Wyckoff
     ├── Divergence
     ├── Volume
     ├── Volatility
     ├── Dominance
     ├── Sentiment
     └── Patterns
          ↓
      EvidenceRecord
          ↓
      EvidenceRegistry
          ↓
      EvidenceScorer
          ↓
      ConfluenceEngine
          ↓
      MarketHypothesis
          ↓
      Decision Engine
