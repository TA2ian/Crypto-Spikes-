from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
)

from decision_v2 import (
    DecisionAction,
    DecisionDirection,
    DecisionEngine,
    DecisionGrade,
    EntryType,
)


def make_evidence(
    name: str,
) -> EvidenceRecord:

    return EvidenceRecord(
        category=EvidenceCategory.STRUCTURE,
        polarity=EvidencePolarity.BULLISH,
        name=name,
        strength=1.0,
        reliability=1.0,
        freshness=1.0,
        timeframe="4h",
        source="test",
    )


def test_accepts_strong_setup() -> None:

    evidence = [
        make_evidence("Structure"),
        make_evidence("Divergence"),
        make_evidence("FVG"),
        make_evidence("Volume"),
        make_evidence("Trend"),
        make_evidence("CVD"),
    ]

    result = DecisionEngine().evaluate(
        evidence=evidence,
        confluence_score=0.90,
        hypothesis_polarity=EvidencePolarity.BULLISH,
        entry_type=EntryType.INITIAL,
    )

    assert result.action == DecisionAction.ACCEPT

    assert result.direction == DecisionDirection.LONG

    assert result.grade == DecisionGrade.A_PLUS

    assert result.accepted is True

    assert result.entry_type == EntryType.INITIAL

    assert result.explanation


def test_rejects_weak_setup() -> None:

    evidence = [
        make_evidence("Single Signal"),
    ]

    result = DecisionEngine().evaluate(
        evidence=evidence,
        confluence_score=0.30,
        hypothesis_polarity=EvidencePolarity.BULLISH,
    )

    assert result.action == DecisionAction.REJECT

    assert result.accepted is False

    assert result.grade == DecisionGrade.INVALID


def test_bearish_setup_returns_short() -> None:

    evidence = [
        EvidenceRecord(
            category=EvidenceCategory.STRUCTURE,
            polarity=EvidencePolarity.BEARISH,
            name="Bearish Structure",
            strength=1.0,
            reliability=1.0,
            freshness=1.0,
            timeframe="4h",
            source="test",
        )
        for _ in range(3)
    ]

    result = DecisionEngine().evaluate(
        evidence=evidence,
        confluence_score=0.70,
        hypothesis_polarity=EvidencePolarity.BEARISH,
    )

    assert result.direction == DecisionDirection.SHORT
