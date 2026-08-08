from evidence_v2 import (
    ConfluenceEngine,
    ConfluenceStrength,
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
    HypothesisEngine,
)


def bullish(
    name: str,
    strength: float,
) -> EvidenceRecord:

    return EvidenceRecord(
        category=EvidenceCategory.STRUCTURE,
        polarity=EvidencePolarity.BULLISH,
        name=name,
        strength=strength,
        reliability=1.0,
        freshness=1.0,
        timeframe="4h",
        source="test",
    )


def bearish(
    name: str,
    strength: float,
) -> EvidenceRecord:

    return EvidenceRecord(
        category=EvidenceCategory.RESISTANCE
        if hasattr(
            EvidenceCategory,
            "RESISTANCE",
        )
        else EvidenceCategory.STRUCTURE,
        polarity=EvidencePolarity.BEARISH,
        name=name,
        strength=strength,
        reliability=1.0,
        freshness=1.0,
        timeframe="4h",
        source="test",
    )


def test_bullish_confluence() -> None:
    evidence = [
        bullish("HTF Trend", 1.0),
        bullish("Hidden Divergence", 0.8),
        bullish("Bullish FVG", 0.7),
    ]

    result = ConfluenceEngine().evaluate(evidence)

    assert result.polarity == EvidencePolarity.BULLISH
    assert result.score > 0.5
    assert result.strength in {
        ConfluenceStrength.STRONG,
        ConfluenceStrength.VERY_STRONG,
    }


def test_conflicting_evidence_is_recorded() -> None:
    evidence = [
        bullish("HTF Trend", 1.0),
        bullish("Divergence", 0.8),
        bearish("Major Resistance", 0.9),
    ]

    result = ConfluenceEngine().evaluate(evidence)

    assert result.polarity == EvidencePolarity.BULLISH
    assert len(result.supporting_evidence) == 2
    assert len(result.conflicting_evidence) == 1


def test_insufficient_evidence_is_neutral() -> None:
    evidence = [
        bullish("Single Signal", 1.0),
    ]

    result = ConfluenceEngine(
        minimum_evidence=2
    ).evaluate(evidence)

    assert result.polarity == EvidencePolarity.NEUTRAL
    assert result.score == 0.0


def test_hypothesis_is_explainable() -> None:
    evidence = [
        bullish("Structure", 1.0),
        bullish("Divergence", 0.9),
    ]

    confluence = ConfluenceEngine().evaluate(
        evidence
    )

    hypothesis = HypothesisEngine().build(
        confluence
    )

    assert hypothesis.polarity == EvidencePolarity.BULLISH
    assert hypothesis.confidence > 0
    assert hypothesis.thesis
    assert hypothesis.supporting_evidence
