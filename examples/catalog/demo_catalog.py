from __future__ import annotations

from agent_chassis.models import (
    AgentProfile,
    GraphDefinition,
    GraphEdge,
    GraphNode,
    KnowledgeRecord,
    RegistryStatus,
    ToolDefinition,
    ToolRisk,
    KnowledgeStatus,
)

AGENTS = [
    AgentProfile(
        id="content-operator",
        name="Content Operator Agent",
        domain="content production",
        responsibility=(
            "Maintain domain knowledge, run registered tools, produce drafts, "
            "pause for human gates, publish approved output, and learn from feedback."
        ),
        model="project-configurable",
        knowledge_base_id="kb-content-production",
        version=1,
        metadata={"status": "active", "source": "catalog"},
    )
]

TOOLS = [
    ToolDefinition(
        id="crawler.fetch_sources",
        name="Fetch Sources",
        description="Crawler adapter placeholder; use Crawl4AI/Crawlee for real projects.",
        input_schema={"type": "object", "properties": {"sources": {"type": "array"}}},
        risk=ToolRisk.read,
        requires_approval=False,
        command="builtin:crawler.fetch_sources",
        tags=["crawler", "evidence"],
        version=1,
        metadata={"source": "catalog"},
    ),
    ToolDefinition(
        id="knowledge.extract_facts",
        name="Extract Facts",
        description="Extract candidate facts with evidence, confidence, and source counts.",
        input_schema={"type": "object", "properties": {"raw_artifact_id": {"type": "string"}}},
        risk=ToolRisk.write,
        requires_approval=False,
        command="builtin:knowledge.extract_facts",
        tags=["knowledge", "candidate"],
        version=1,
        metadata={"source": "catalog"},
    ),
    ToolDefinition(
        id="draft.generate",
        name="Generate Draft",
        description="Generate structured draft output from knowledge and strategy context.",
        input_schema={"type": "object", "properties": {"topic": {"type": "string"}}},
        risk=ToolRisk.write,
        requires_approval=False,
        command="builtin:draft.generate",
        tags=["draft", "content"],
        version=1,
        metadata={"source": "catalog"},
    ),
    ToolDefinition(
        id="publisher.publish",
        name="Publish Output",
        description="Publish an approved artifact to an external channel.",
        input_schema={"type": "object", "properties": {"artifact_id": {"type": "string"}}},
        risk=ToolRisk.publish,
        requires_approval=True,
        command="builtin:publisher.publish",
        tags=["publish", "high-risk"],
        version=1,
        metadata={"source": "catalog"},
    ),
]

KNOWLEDGE = [
    KnowledgeRecord(
        id="kr-wheel-first",
        status=KnowledgeStatus.stable,
        subject="Wheel-first development",
        summary="Before new architecture/features, search GitHub mature wheels and prefer reuse/thin wrappers.",
        evidence_count=1,
        confidence=0.96,
        source="Joy directive",
    ),
    KnowledgeRecord(
        id="kr-admin-ui",
        status=KnowledgeStatus.stable,
        subject="Admin UI template",
        summary="Use satnaing/shadcn-admin directly for backend/admin UI instead of hand-rolling.",
        evidence_count=1,
        confidence=0.96,
        source="Joy directive / satnaing/shadcn-admin",
    ),
]

GRAPH = GraphDefinition(
    id="agent-production-loop",
    name="Agent Production Loop",
    description="Reusable FSM/cyclic graph for knowledge-driven Agent production systems.",
    nodes=[
        GraphNode(
            id="collect_source",
            title="Collect Source",
            kind="collect",
            description="Fetch raw data from configured sources and keep evidence.",
            tool_ids=["crawler.fetch_sources"],
        ),
        GraphNode(
            id="normalize",
            title="Normalize",
            kind="normalize",
            description="Clean, dedupe, and convert raw data into normalized records.",
        ),
        GraphNode(
            id="strategy_judge",
            title="Strategy Judge",
            kind="judge",
            description="Decide whether evidence is enough or more data is needed.",
            tool_ids=["knowledge.extract_facts"],
        ),
        GraphNode(
            id="draft_generate",
            title="Draft Generate",
            kind="draft",
            description="Generate a structured draft artifact.",
            tool_ids=["draft.generate"],
        ),
        GraphNode(
            id="quality_check",
            title="Quality Check",
            kind="quality_check",
            description="Run deterministic and LLM-based checks before human review.",
        ),
        GraphNode(
            id="human_review",
            title="Human Review",
            kind="human_gate",
            description="Interrupt and wait for approve/reject/edit/need-more-data.",
            interrupt=True,
        ),
        GraphNode(
            id="publish",
            title="Publish",
            kind="publish",
            description="Publish approved artifact and write publish log.",
            tool_ids=["publisher.publish"],
        ),
        GraphNode(
            id="feedback_ingest",
            title="Feedback Ingest",
            kind="feedback",
            description="Sediment human edits, corrections, publish results, and failures into knowledge.",
        ),
        GraphNode(id="done", title="Done", kind="done", description="Run completed."),
    ],
    edges=[
        GraphEdge(**{"from": "collect_source", "to": "normalize"}),
        GraphEdge(**{"from": "normalize", "to": "strategy_judge"}),
        GraphEdge(**{"from": "strategy_judge", "to": "draft_generate", "condition": "enough_evidence"}),
        GraphEdge(**{"from": "strategy_judge", "to": "collect_source", "condition": "need_more_data", "label": "loop: collect more"}),
        GraphEdge(**{"from": "draft_generate", "to": "quality_check"}),
        GraphEdge(**{"from": "quality_check", "to": "human_review"}),
        GraphEdge(**{"from": "human_review", "to": "publish", "condition": "approve"}),
        GraphEdge(**{"from": "human_review", "to": "draft_generate", "condition": "edit", "label": "loop: revise"}),
        GraphEdge(**{"from": "human_review", "to": "strategy_judge", "condition": "reject", "label": "loop: rejudge"}),
        GraphEdge(**{"from": "human_review", "to": "collect_source", "condition": "need_more_data", "label": "loop: collect more"}),
        GraphEdge(**{"from": "publish", "to": "feedback_ingest"}),
        GraphEdge(**{"from": "feedback_ingest", "to": "done"}),
    ],
    status=RegistryStatus.active,
    version=1,
    metadata={"source": "catalog"},
)
