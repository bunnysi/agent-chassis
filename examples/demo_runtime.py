from __future__ import annotations

from agent_chassis.models import (
    AgentEvent,
    AgentEventType,
    AgentRun,
    HumanDecision,
    RunArtifact,
    RunStatus,
    now_iso,
)


class RuntimeState(dict):
    pass


def _event(run: AgentRun, event_type: AgentEventType, node_id: str, title: str, message: str, payload: dict | None = None) -> None:
    run.events.append(
        AgentEvent(
            run_id=run.id,
            type=event_type,
            node_id=node_id,
            title=title,
            message=message,
            payload=payload or {},
        )
    )
    run.updated_at = now_iso()


def _touch(run: AgentRun, status: RunStatus, node_id: str) -> None:
    run.status = status
    run.current_node_id = node_id
    run.updated_at = now_iso()


def collect_source(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "collect_source")
    _event(run, AgentEventType.node_started, "collect_source", "Collect source", "Fetching configured sources.")
    run.artifacts.append(
        RunArtifact(
            node_id="collect_source",
            title="Raw source bundle",
            type="raw",
            summary=f"Collected {len(state.get('sources') or []) or 1} source(s) for {state.get('topic')}",
            payload={"sources": state.get("sources") or ["demo://source"]},
        )
    )
    _event(run, AgentEventType.tool_called, "collect_source", "crawler.fetch_sources", "Raw source artifact created.")
    return state


def normalize(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "normalize")
    run.artifacts.append(
        RunArtifact(
            node_id="normalize",
            title="Normalized records",
            type="normalized",
            summary="Raw data normalized, deduped, and source-tagged.",
        )
    )
    _event(run, AgentEventType.artifact_created, "normalize", "Normalized", "Normalized records are ready.")
    return state


def strategy_judge(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "strategy_judge")
    evidence_count = max(int(state.get("evidence_count") or 0), len(state.get("sources") or []), 1)
    state["evidence_count"] = evidence_count
    _event(
        run,
        AgentEventType.node_started,
        "strategy_judge",
        "Strategy judge",
        f"Evidence count={evidence_count}; enough for draft in this demo runtime.",
        {"evidence_count": evidence_count},
    )
    return state


def route_after_strategy(state: dict) -> str:
    return "draft_generate" if int(state.get("evidence_count") or 0) >= 1 else "collect_source"


def draft_generate(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "draft_generate")
    run.artifacts.append(
        RunArtifact(
            node_id="draft_generate",
            title="Draft artifact",
            type="draft",
            summary=f"Draft generated for topic: {state.get('topic')}",
            payload={"topic": state.get("topic"), "status": "draft"},
        )
    )
    _event(run, AgentEventType.artifact_created, "draft_generate", "Draft generated", "Draft artifact is waiting for quality check.")
    return state


def quality_check(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "quality_check")
    run.artifacts.append(
        RunArtifact(
            node_id="quality_check",
            title="Quality review",
            type="review",
            summary="Deterministic checks passed in demo runtime; human gate is still required.",
        )
    )
    _event(run, AgentEventType.artifact_created, "quality_check", "Quality checked", "Quality review artifact created.")
    return state


def human_review(state: dict) -> dict:
    run = state["run"]
    if state.get("auto_approve"):
        state["human_decision"] = HumanDecision.approve.value
        _event(run, AgentEventType.human_decision, "human_review", "Auto approved", "auto_approve=true skipped manual wait.", {"decision": HumanDecision.approve.value})
        return state
    _touch(run, RunStatus.waiting_for_human, "human_review")
    run.pending_human_actions = [
        HumanDecision.approve,
        HumanDecision.edit,
        HumanDecision.reject,
        HumanDecision.need_more_data,
    ]
    _event(run, AgentEventType.approval_required, "human_review", "Human gate required", "Waiting for approve/edit/reject/need_more_data.")
    return state


def route_after_human(state: dict) -> str:
    decision = state.get("human_decision")
    if decision == HumanDecision.approve.value:
        return "publish"
    if decision == HumanDecision.edit.value:
        return "draft_generate"
    if decision == HumanDecision.need_more_data.value:
        return "collect_source"
    if decision == HumanDecision.reject.value:
        return "strategy_judge"
    return "__end__"


def publish(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.publishing, "publish")
    run.pending_human_actions = []
    run.artifacts.append(
        RunArtifact(
            node_id="publish",
            title="Publish log",
            type="publish_log",
            summary="Approved draft published by demo runtime placeholder.",
        )
    )
    _event(run, AgentEventType.published, "publish", "Published", "Publish log created.")
    return state


def feedback_ingest(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.running, "feedback_ingest")
    run.artifacts.append(
        RunArtifact(
            node_id="feedback_ingest",
            title="Feedback ingest",
            type="feedback",
            summary="Feedback ingested for future runs.",
        )
    )
    _event(run, AgentEventType.feedback_ingested, "feedback_ingest", "Feedback ingested", "Feedback has been recorded.")
    return state


def done(state: dict) -> dict:
    run = state["run"]
    _touch(run, RunStatus.completed, "done")
    _event(run, AgentEventType.run_completed, "done", "Run completed", "Demo run completed.")
    return state


NODE_HANDLERS = {
    "collect_source": collect_source,
    "normalize": normalize,
    "strategy_judge": strategy_judge,
    "draft_generate": draft_generate,
    "quality_check": quality_check,
    "human_review": human_review,
    "publish": publish,
    "feedback_ingest": feedback_ingest,
    "done": done,
}

ROUTE_HANDLERS = {
    "strategy_judge": route_after_strategy,
    "human_review": route_after_human,
}
