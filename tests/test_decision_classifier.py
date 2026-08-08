from decision_v2 import (
    DecisionClassifier,
    DecisionGrade,
    DecisionThresholds,
)


def test_a_plus_classification() -> None:

    classifier = DecisionClassifier(
        DecisionThresholds()
    )

    result = classifier.classify(
        confluence_score=0.90,
        supporting_evidence_count=6,
        accepted=True,
    )

    assert result == DecisionGrade.A_PLUS


def test_a_classification() -> None:

    classifier = DecisionClassifier(
        DecisionThresholds()
    )

    result = classifier.classify(
        confluence_score=0.75,
        supporting_evidence_count=4,
        accepted=True,
    )

    assert result == DecisionGrade.A


def test_invalid_rejected_decision() -> None:

    classifier = DecisionClassifier(
        DecisionThresholds()
    )

    result = classifier.classify(
        confluence_score=0.90,
        supporting_evidence_count=6,
        accepted=False,
    )

    assert result == DecisionGrade.INVALID
