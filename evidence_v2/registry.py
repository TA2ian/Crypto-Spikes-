from __future__ import annotations

from .models import EvidenceRecord


class EvidenceRegistry:
    """
    Stores and manages evidence for one analysis cycle.
    """

    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}

    def add(
        self,
        evidence: EvidenceRecord,
    ) -> bool:
        """
        Add evidence.

        Returns False if the same evidence ID already exists.
        """

        if evidence.evidence_id in self._records:
            return False

        self._records[evidence.evidence_id] = evidence

        return True

    def get(
        self,
        evidence_id: str,
    ) -> EvidenceRecord | None:

        return self._records.get(evidence_id)

    def all(self) -> list[EvidenceRecord]:
        return list(self._records.values())

    def clear(self) -> None:
        self._records.clear()

    def __len__(self) -> int:
        return len(self._records)
