from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
)

from decision_v2 import (
    DecisionGates,
    DecisionThresholds,
)


def evidence(
    polarity: EvidencePolarity,
    name: str,
) -> EvidenceRecord:

    return EvidenceRecord(
        category=EvidenceCategory.STRUCTURE,
        polarity=polarity,
        name=name,
        strength=1.0,
        reliability=1.0,
        freshness=1.0,
        timeframe="4h",
        source="test",
    )


def test_gates_pass_for_strong_bullish_setup() -> None:

    items = [
        evidence(
            EvidencePolarity.BULLISH,
            "HTF Trend",
        ),
        evidence(
            EvidencePolarity.BULLISH,
            "Structure",
        ),
        evidence(
            EvidencePolarity.BULLISH,
            "Divergence",
        ),
    ]

    result = DecisionGates(
        DecisionThresholds()
    ).evaluate(
        evidence=items,
        confluence_score=0.80,
        hypothesis_polarity=EvidencePolarity.BULLISH,
    )

    assert not result.rejection_reasons


def test_gates_reject_low_confluence() -> None:

    items = [
        evidence(
            EvidencePolarity.BULLISH,
            "Trend",
        ),
        evidence(
            EvidencePolarity.BULLISH,
            "Structure",
        ),
        evidence(
            EvidencePolarity.BULLISH,
            "Volume",
        ),
    ]

    result = DecisionGates(
        DecisionThresholds()
    ).evaluate(
        evidence=items,
        confluence_score=0.30,
        hypothesis_polarity=EvidencePolarity.BULLISH,
    )

    assert result.rejection_reasons
