from __future__ import annotations

from typing import Any, TypedDict

from agentgraph_core.demo_catalog import GRAPH
from agentgraph_core.graph_registry import GraphRuntimeSpec, build_runtime_graph, default_entry_node

from agentgraph_core.models import (
    AgentEvent,
    AgentEventType,
    AgentRun,
    HumanDecision,
    RunArtifact,
    RunStatus,
    now_iso,
)


class RuntimeState(TypedDict, total=False):
    run: AgentRun
    topic: str
    sources: list[str]
    evidence_count: int
    auto_approve: bool
    human_decision: str
    note: str | None


def _event(run: AgentRun, event_type: AgentEventType, node_id: str, title: str, message: str, payload: dict[str, Any] | None = None) -> None:
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


def collect_source(state: RuntimeState) -> RuntimeState:
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


def normalize(state: RuntimeState) -> RuntimeState:
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


def strategy_judge(state: RuntimeState) -> RuntimeState:
    run = state["run"]
    _touch(run, RunStatus.running, "strategy_judge")
    evidence_count = max(int(state.get("evidence_count") or 0), len(state.get("sources") or []), 1)
    state["evidence_count"] = evidence_count
    _event(
        run,
        AgentEventType.node_started,
        "strategy_judge",
        "Strategy judge",
        f"Evidence count={evidence_count}; enough for draft in this v0 runtime.",
        {"evidence_count": evidence_count},
    )
    return state


def route_after_strategy(state: RuntimeState) -> str:
    return "draft_generate" if int(state.get("evidence_count") or 0) >= 1 else "collect_source"


def draft_generate(state: RuntimeState) -> RuntimeState:
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


def quality_check(state: RuntimeState) -> RuntimeState:
    run = state["run"]
    _touch(run, RunStatus.running, "quality_check")
    run.artifacts.append(
        RunArtifact(
            node_id="quality_check",
            title="Quality review",
            type="review",
            summary="Deterministic checks passed in v0 demo runtime; human gate is still required.",
        )
    )
    _event(run, AgentEventType.artifact_created, "quality_check", "Quality checked", "Quality review artifact created.")
    return state


def human_review(state: RuntimeState) -> RuntimeState:
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


def route_after_human(state: RuntimeState) -> str:
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


def publish(state: RuntimeState) -> RuntimeState:
    run = state["run"]
    _touch(run, RunStatus.publishing, "publish")
    run.pending_human_actions = []
    run.artifacts.append(
        RunArtifact(
            node_id="publish",
            title="Publish log",
            type="publish_log",
            summary="Approved draft published by v0 runtime placeholder.",
        )
    )
    _event(run, AgentEventType.published, "publish", "Published", "Publish log created.")
    return state


def feedback_ingest(state: RuntimeState) -> RuntimeState:
    run = state["run"]
    _touch(run, RunStatus.running, "feedback_ingest")
    run.artifacts.append(
        RunArtifact(
            node_id="feedback_ingest",
            title="Feedback record",
            type="feedback",
            summary="Human decision and publish result sedimented into feedback ledger placeholder.",
        )
    )
    _event(run, AgentEventType.feedback_ingested, "feedback_ingest", "Feedback ingested", "Feedback ledger updated.")
    return state


def done(state: RuntimeState) -> RuntimeState:
    run = state["run"]
    _touch(run, RunStatus.completed, "done")
    _event(run, AgentEventType.run_completed, "done", "Run completed", "Agent production loop completed.")
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

RUNTIME_SPEC = GraphRuntimeSpec(
    definition=GRAPH,
    entry_node_id=default_entry_node(GRAPH),
    node_handlers=NODE_HANDLERS,
    route_handlers=ROUTE_HANDLERS,
)

COMPILED_GRAPH = build_runtime_graph(RUNTIME_SPEC)


class AgentGraphRuntime:
    def __init__(self, spec: GraphRuntimeSpec = RUNTIME_SPEC):
        self.spec = spec
        self.graph = COMPILED_GRAPH if spec is RUNTIME_SPEC else build_runtime_graph(spec)

    def start(self, *, agent_id: str, topic: str, sources: list[str], auto_approve: bool = False) -> AgentRun:
        run = AgentRun(agent_id=agent_id, graph_id=self.spec.definition.id, status=RunStatus.running)
        _event(run, AgentEventType.run_started, self.spec.entry_node_id, "Run started", "AgentGraph run started.")
        state: RuntimeState = {"run": run, "topic": topic, "sources": sources, "auto_approve": auto_approve}
        result = self.graph.invoke({"payload": state}, {"recursion_limit": 25})
        return result["payload"]["run"]

    def resume(self, run: AgentRun, decision: HumanDecision, note: str | None = None) -> AgentRun:
        _event(run, AgentEventType.human_decision, "human_review", f"Human decision: {decision.value}", note or "", {"decision": decision.value})
        if decision == HumanDecision.approve:
            state: RuntimeState = {
                "run": run,
                "topic": run.state.get("topic") or "resumed topic",
                "sources": run.state.get("sources") or [],
                "human_decision": decision.value,
                "note": note,
            }
            result = self.graph.invoke({"payload": state}, {"recursion_limit": 25})
            return result["payload"]["run"]

        run.pending_human_actions = []
        restart_state: RuntimeState = {
            "run": run,
            "topic": run.state.get("topic") or "resumed topic",
            "sources": run.state.get("sources") or [],
            "note": note,
        }
        if decision == HumanDecision.edit:
            for handler in (draft_generate, quality_check, human_review):
                handler(restart_state)
            return run
        if decision == HumanDecision.need_more_data:
            for handler in (collect_source, normalize, strategy_judge, draft_generate, quality_check, human_review):
                handler(restart_state)
            return run
        if decision == HumanDecision.reject:
            for handler in (strategy_judge, draft_generate, quality_check, human_review):
                handler(restart_state)
            return run
        _touch(run, RunStatus.failed, "human_review")
        return run
