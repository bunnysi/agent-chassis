from __future__ import annotations

from uuid import uuid4

from .demo_catalog import KNOWLEDGE
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
    """Knowledge ledger policy for candidate -> stable -> rejected flow."""

    def seed_records(self) -> list[KnowledgeRecord]:
        return KNOWLEDGE

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
