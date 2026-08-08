"""
Tests for V2 domain models.
"""

from datetime import datetime, timezone

import pytest

from models.asset_profile import (
    AssetProfile,
    HalalStatus,
    MarketRegime,
    StructuralBias,
    TrendDirection,
)

from models.market_context import (
    MarketContext,
    RiskRegime,
)

from models.evidence import (
    DivergenceType,
    Evidence,
    EvidenceDirection,
    EvidenceType,
)

from models.decision import (
    Decision,
    DecisionAction,
    RiskLevel,
)

from models.trade_case import (
    EntryType,
    TradeCase,
    TradeState,
)


def test_asset_profile_creation() -> None:
    asset = AssetProfile(
        symbol="btc",
        exchange="OKX",
        halal_status=HalalStatus.APPROVED,
    )

    assert asset.symbol == "BTC"
    assert asset.exchange == "OKX"
    assert asset.halal_status == HalalStatus.APPROVED
    assert asset.is_tradeable() is True


def test_asset_profile_rejects_empty_symbol() -> None:
    with pytest.raises(ValueError):
        AssetProfile(
            symbol="",
            exchange="OKX",
        )


def test_asset_profile_state_update() -> None:
    asset = AssetProfile(
        symbol="ETH",
        exchange="BYBIT",
    )

    asset.update_state(
        macro_trend=TrendDirection.BULLISH,
        structural_bias=StructuralBias.BULLISH,
        market_regime=MarketRegime.TRENDING,
    )

    assert asset.macro_trend == TrendDirection.BULLISH
    assert asset.structural_bias == StructuralBias.BULLISH
    assert asset.market_regime == MarketRegime.TRENDING


def test_market_context_validation() -> None:
    context = MarketContext(
        btc_trend="bullish",
        btc_dominance=55.5,
        usdt_dominance=4.2,
        fear_greed_index=65,
        risk_regime=RiskRegime.RISK_ON,
    )

    assert context.btc_dominance == 55.5
    assert context.fear_greed_index == 65


def test_market_context_rejects_invalid_fear_greed() -> None:
    with pytest.raises(ValueError):
        MarketContext(
            fear_greed_index=120,
        )


def test_evidence_creation() -> None:
    evidence = Evidence(
        type=EvidenceType.DIVERGENCE,
        subtype=DivergenceType.HIDDEN,
        direction=EvidenceDirection.BULLISH,
        strength=0.90,
        timeframe="4h",
        source="divergence_engine",
        reliability=0.95,
        freshness=0.90,
    )

    assert evidence.type == EvidenceType.DIVERGENCE
    assert evidence.subtype == "hidden"
    assert evidence.is_bullish is True
    assert 0 <= evidence.quality <= 1


def test_evidence_rejects_invalid_strength() -> None:
    with pytest.raises(ValueError):
        Evidence(
            type=EvidenceType.VOLUME,
            direction=EvidenceDirection.BULLISH,
            strength=1.5,
            timeframe="1h",
            source="volume_engine",
        )


def test_decision_creation() -> None:
    evidence = Evidence(
        type=EvidenceType.TREND,
        direction=EvidenceDirection.BULLISH,
        strength=0.9,
        timeframe="1d",
        source="trend_engine",
    )

    decision = Decision(
        action=DecisionAction.BUY,
        confidence=0.87,
        risk_level=RiskLevel.MODERATE,
        reasoning="Higher timeframe trend supports the setup.",
    )

    decision.add_evidence(
        evidence.evidence_id,
        supporting=True,
    )

    assert decision.action == DecisionAction.BUY
    assert decision.is_actionable() is True
    assert evidence.evidence_id in decision.evidence_ids
    assert evidence.evidence_id in decision.supporting_evidence


def test_actionable_decision_requires_reasoning() -> None:
    with pytest.raises(ValueError):
        Decision(
            action=DecisionAction.BUY,
            confidence=0.8,
            risk_level=RiskLevel.MODERATE,
        )


def test_trade_case_lifecycle() -> None:
    trade = TradeCase(
        symbol="BTC",
        direction="long",
        entry_price=100_000,
        stop_loss=97_000,
        tp1=103_000,
        tp2=106_000,
        tp3=110_000,
        entry_type=EntryType.FIRST_ENTRY,
    )

    assert trade.state == TradeState.WAITING

    trade.mark_ready()
    assert trade.state == TradeState.READY

    trade.mark_entry()
    assert trade.state == TradeState.ENTRY

    trade.activate()
    assert trade.state == TradeState.ACTIVE
    assert trade.is_active() is True


def test_trade_targets_are_locked_after_entry() -> None:
    trade = TradeCase(
        symbol="BTC",
        direction="long",
        entry_price=100_000,
        stop_loss=97_000,
        tp1=103_000,
    )

    trade.mark_ready()
    trade.mark_entry()

    with pytest.raises(ValueError):
        trade.update_targets(
            tp1=105_000,
        )


def test_trade_targets_can_be_updated_before_entry() -> None:
    trade = TradeCase(
        symbol="ETH",
        direction="long",
        entry_price=3_000,
        stop_loss=2_850,
        tp1=3_100,
    )

    trade.mark_ready()

    trade.update_targets(
        tp1=3_150,
        tp2=3_300,
    )

    assert trade.tp1 == 3_150
    assert trade.tp2 == 3_300


def test_trade_reentry_type_is_supported() -> None:
    trade = TradeCase(
        symbol="SOL",
        direction="long",
        entry_price=150,
        stop_loss=142,
        entry_type=EntryType.RE_ENTRY,
    )

    assert trade.entry_type == EntryType.RE_ENTRY


def test_trade_close() -> None:
    trade = TradeCase(
        symbol="BTC",
        direction="long",
        entry_price=100_000,
        stop_loss=97_000,
    )

    trade.mark_ready()
    trade.mark_entry()
    trade.activate()
    trade.close()

    assert trade.state == TradeState.CLOSED
    assert trade.closed_at is not None


def test_evidence_support_and_conflict_are_separate() -> None:
    supporting = Evidence(
        type=EvidenceType.TREND,
        direction=EvidenceDirection.BULLISH,
        strength=0.8,
        timeframe="4h",
        source="trend_engine",
    )

    conflicting = Evidence(
        type=EvidenceType.RESISTANCE,
        direction=EvidenceDirection.BEARISH,
        strength=0.7,
        timeframe="4h",
        source="structure_engine",
    )

    decision = Decision(
        action=DecisionAction.WATCH,
        confidence=0.6,
        risk_level=RiskLevel.HIGH,
    )

    decision.add_evidence(
        supporting.evidence_id,
        supporting=True,
    )

    decision.add_evidence(
        conflicting.evidence_id,
        supporting=False,
    )

    assert supporting.evidence_id in decision.supporting_evidence
    assert conflicting.evidence_id in decision.conflicting_evidence
    assert decision.has_conflict() is True
