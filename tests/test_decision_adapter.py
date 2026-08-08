from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
)

from models.decision import (
    DecisionAction as DomainDecisionAction,
)

from decision_v2 import (
    DecisionDirection,
    DecisionEngine,
    EntryType,
    to_domain_decision,
)


def test_v2_decision_adapts_to_domain_decision() -> None:

    evidence = [
        EvidenceRecord(
            category=EvidenceCategory.STRUCTURE,
            polarity=EvidencePolarity.BULLISH,
            name=name,
            strength=1.0,
            reliability=1.0,
            freshness=1.0,
            timeframe="4h",
            source="test",
        )
        for name in (
            "Structure",
            "Divergence",
            "Volume",
        )
    ]

    result = DecisionEngine().evaluate(
        evidence=evidence,
        confluence_score=0.70,
        hypothesis_polarity=EvidencePolarity.BULLISH,
        entry_type=EntryType.INITIAL,
    )

    domain = to_domain_decision(result)

    assert result.action.value == "accept"

    assert (
        result.direction
        == DecisionDirection.LONG
    )

    assert (
        domain.action
        == DomainDecisionAction.BUY
    )

    assert (
        domain.confidence
        == result.confidence
    )

    assert (
        domain.supporting_evidence
        == list(
            result.supporting_evidence
        )
    )
