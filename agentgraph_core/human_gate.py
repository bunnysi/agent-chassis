from __future__ import annotations

from .models import AgentRun, HumanDecision, HumanGateReview, HumanGateReviewRequest, HumanGateStatus, RunStatus, now_iso


class HumanGateRegistry:
    """Standard human-gate contract for AgentGraph runs.

    Runtime nodes still decide what the workflow does after a decision; this layer
    standardizes the review payload, allowed actions, status, score, and audit log
    so the admin UI/API can inspect gates without reading raw events.
    """

    def create_for_run(self, run: AgentRun, *, requested_by: str = "runtime") -> HumanGateReview | None:
        if run.status != RunStatus.waiting_for_human:
            return None
        return HumanGateReview(
            run_id=run.id,
            node_id=run.current_node_id,
            allowed_decisions=run.pending_human_actions,
            requested_by=requested_by,
        )

    def apply_decision(self, review: HumanGateReview, request: HumanGateReviewRequest) -> HumanGateReview:
        if review.status.value != "pending":
            raise ValueError("human gate review is already resolved")
        if request.decision not in review.allowed_decisions:
            raise ValueError("decision is not allowed for this human gate")
        review.status = HumanGateStatus.resolved
        review.decision = request.decision
        review.note = request.note
        review.score = request.score
        review.edited_payload = request.edited_payload
        review.resolved_by = request.resolved_by
        review.resolved_at = now_iso()
        review.updated_at = now_iso()
        return review
