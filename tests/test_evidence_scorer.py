from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceScorer,
)


def test_bullish_score() -> None:
    evidence = [
        EvidenceRecord(
            category=EvidenceCategory.DIVERGENCE,
            polarity=EvidencePolarity.BULLISH,
            name="Hidden Divergence",
            strength=1.0,
            reliability=1.0,
            freshness=1.0,
            timeframe="4h",
            source="test",
        ),
        EvidenceRecord(
            category=EvidenceCategory.VOLUME,
            polarity=EvidencePolarity.BULLISH,
            name="Volume Expansion",
            strength=0.5,
            reliability=1.0,
            freshness=1.0,
            timeframe="4h",
            source="test",
        ),
    ]

    result = EvidenceScorer().score(evidence)

    assert result.bullish == 1.5
    assert result.bearish == 0.0


def test_effective_score_uses_all_components() -> None:
    evidence = EvidenceRecord(
        category=EvidenceCategory.TREND,
        polarity=EvidencePolarity.BULLISH,
        name="HTF Trend",
        strength=0.8,
        reliability=0.9,
        freshness=0.5,
        timeframe="1d",
        source="test",
        weight=1.0,
    )

    assert evidence.effective_score == 0.36
