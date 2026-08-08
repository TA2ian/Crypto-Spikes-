from evidence_v2 import (
    EvidenceCategory,
    EvidencePolarity,
    EvidenceRecord,
    EvidenceRegistry,
)


def create_evidence() -> EvidenceRecord:
    return EvidenceRecord(
        category=EvidenceCategory.DIVERGENCE,
        polarity=EvidencePolarity.BULLISH,
        name="Hidden Bullish Divergence",
        strength=0.90,
        reliability=0.90,
        freshness=1.0,
        timeframe="4h",
        source="divergence_v2",
    )


def test_registry_adds_evidence() -> None:
    registry = EvidenceRegistry()

    evidence = create_evidence()

    assert registry.add(evidence) is True
    assert len(registry) == 1


def test_registry_prevents_duplicate_ids() -> None:
    registry = EvidenceRegistry()

    evidence = create_evidence()

    assert registry.add(evidence) is True
    assert registry.add(evidence) is False

    assert len(registry) == 1
