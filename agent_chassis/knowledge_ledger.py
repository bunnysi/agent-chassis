from __future__ import annotations

from uuid import uuid4

from .models import (
    KnowledgeDecisionRequest,
    KnowledgeEvidence,
    KnowledgeRecord,
    KnowledgeRecordRequest,
    KnowledgeStatus,
    now_iso,
)

PROMOTE_MIN_CONFIDENCE = 0.78
PROMOTE_MIN_EVIDENCE = 2


class KnowledgeLedger:
    """Policy layer for candidate -> stable -> rejected knowledge flow.

    Seed records are explicit constructor input so the core package does not depend
    on demo or project-specific knowledge.
    """

    def __init__(self, seed_records: list[KnowledgeRecord] | None = None) -> None:
        self._seed_records = list(seed_records or [])

    def seed_records(self) -> list[KnowledgeRecord]:
        return list(self._seed_records)

    def create_candidate(self, request: KnowledgeRecordRequest) -> tuple[KnowledgeRecord, list[KnowledgeEvidence]]:
        record_id = f"kr-{uuid4().hex[:10]}"
        evidence = [
            KnowledgeEvidence(
                knowledge_id=record_id,
                source=item.get("source") or request.source,
                quote=item.get("quote") or request.summary,
                url=item.get("url"),
                confidence=float(item.get("confidence", request.confidence)),
            )
            for item in request.evidence
        ]
        record = KnowledgeRecord(
            id=record_id,
            status=KnowledgeStatus.candidate,
            subject=request.subject,
            summary=request.summary,
            evidence_count=len(evidence),
            confidence=request.confidence,
            source=request.source,
            tags=request.tags,
        )
        return record, evidence

    def apply_decision(self, record: KnowledgeRecord, decision: KnowledgeDecisionRequest) -> KnowledgeRecord:
        if decision.decision == "promote":
            if record.confidence < PROMOTE_MIN_CONFIDENCE or record.evidence_count < PROMOTE_MIN_EVIDENCE:
                raise ValueError("promotion requires confidence>=0.78 and evidence_count>=2")
            record.status = KnowledgeStatus.stable
            record.promoted_at = now_iso()
        elif decision.decision == "reject":
            record.status = KnowledgeStatus.rejected
            record.rejected_at = now_iso()
        elif decision.decision == "correct":
            if decision.summary:
                record.summary = decision.summary
            if decision.confidence is not None:
                record.confidence = decision.confidence
            record.correction_count += 1
        record.updated_at = now_iso()
        return record
