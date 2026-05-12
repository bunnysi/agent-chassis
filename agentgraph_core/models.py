from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, Field


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegistryStatus(str, Enum):
    active = "active"
    paused = "paused"
    archived = "archived"


class RunStatus(str, Enum):
    idle = "idle"
    running = "running"
    waiting_for_human = "waiting_for_human"
    publishing = "publishing"
    completed = "completed"
    failed = "failed"


class KnowledgeStatus(str, Enum):
    candidate = "candidate"
    stable = "stable"
    rejected = "rejected"


class ToolRisk(str, Enum):
    read = "read"
    write = "write"
    publish = "publish"


class ToolExecutionStatus(str, Enum):
    queued = "queued"
    running = "running"
    succeeded = "succeeded"
    failed = "failed"
    blocked = "blocked"


class TriggerKind(str, Enum):
    manual = "manual"
    cron = "cron"
    event = "event"


class ScheduledJobStatus(str, Enum):
    active = "active"
    paused = "paused"


class HumanDecision(str, Enum):
    approve = "approve"
    reject = "reject"
    edit = "edit"
    score = "score"
    need_more_data = "need_more_data"


class HumanGateStatus(str, Enum):
    pending = "pending"
    resolved = "resolved"
    cancelled = "cancelled"


class AgentEventType(str, Enum):
    run_started = "run_started"
    node_started = "node_started"
    tool_called = "tool_called"
    artifact_created = "artifact_created"
    approval_required = "approval_required"
    human_decision = "human_decision"
    published = "published"
    feedback_ingested = "feedback_ingested"
    run_completed = "run_completed"
    run_failed = "run_failed"


class AgentProfile(BaseModel):
    id: str
    name: str
    domain: str
    responsibility: str
    model: str
    knowledge_base_id: str
    status: RegistryStatus = RegistryStatus.active
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentProfileRequest(BaseModel):
    id: str | None = None
    name: str
    domain: str
    responsibility: str
    model: str = "project-configurable"
    knowledge_base_id: str
    status: RegistryStatus = RegistryStatus.active
    version: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RegistryStatusRequest(BaseModel):
    status: RegistryStatus


class ToolDefinition(BaseModel):
    id: str
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    risk: ToolRisk
    requires_approval: bool = False
    enabled: bool = True
    command: str | None = None
    adapter: str = "builtin"
    timeout_seconds: int = 60
    tags: list[str] = Field(default_factory=list)
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolDefinitionRequest(BaseModel):
    id: str | None = None
    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    risk: ToolRisk = ToolRisk.read
    requires_approval: bool = False
    enabled: bool = True
    command: str | None = None
    adapter: str = "builtin"
    timeout_seconds: int = 60
    tags: list[str] = Field(default_factory=list)
    version: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolStatusRequest(BaseModel):
    enabled: bool


class ToolExecutionRequest(BaseModel):
    tool_id: str
    run_id: str | None = None
    node_id: str | None = None
    input: dict[str, Any] = Field(default_factory=dict)
    requested_by: str = "manual"
    auto_approve: bool = False


class ToolExecution(BaseModel):
    id: str = Field(default_factory=lambda: f"tool-exec-{uuid4().hex[:10]}")
    tool_id: str
    run_id: str | None = None
    node_id: str | None = None
    status: ToolExecutionStatus = ToolExecutionStatus.queued
    risk: ToolRisk
    requires_approval: bool = False
    input: dict[str, Any] = Field(default_factory=dict)
    output: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None
    requested_by: str = "manual"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)


class ToolExecutionDecisionRequest(BaseModel):
    decision: HumanDecision
    note: str | None = None


class KnowledgeRecord(BaseModel):
    id: str
    status: KnowledgeStatus
    subject: str
    summary: str
    evidence_count: int = 0
    confidence: float = 0.0
    source: str
    updated_at: str = Field(default_factory=now_iso)
    tags: list[str] = Field(default_factory=list)
    promoted_at: str | None = None
    rejected_at: str | None = None
    correction_count: int = 0


class KnowledgeEvidence(BaseModel):
    id: str = Field(default_factory=lambda: f"evidence-{uuid4().hex[:10]}")
    knowledge_id: str
    source: str
    quote: str
    url: str | None = None
    confidence: float = 0.0
    created_at: str = Field(default_factory=now_iso)


class KnowledgeRecordRequest(BaseModel):
    subject: str
    summary: str
    source: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    confidence: float = 0.0
    tags: list[str] = Field(default_factory=list)


class KnowledgeDecisionRequest(BaseModel):
    decision: Literal["promote", "reject", "correct"]
    note: str | None = None
    summary: str | None = None
    confidence: float | None = None


class GraphNode(BaseModel):
    id: str
    title: str
    kind: str
    description: str
    tool_ids: list[str] = Field(default_factory=list)
    interrupt: bool = False


class GraphEdge(BaseModel):
    from_node: str = Field(alias="from")
    to_node: str = Field(alias="to")
    label: str | None = None
    condition: str | None = None


class GraphDefinition(BaseModel):
    id: str
    name: str
    description: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    status: RegistryStatus = RegistryStatus.active
    version: int = 1
    metadata: dict[str, Any] = Field(default_factory=dict)


class GraphDefinitionRequest(BaseModel):
    id: str | None = None
    name: str
    description: str
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    status: RegistryStatus = RegistryStatus.active
    version: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunArtifact(BaseModel):
    id: str = Field(default_factory=lambda: f"artifact-{uuid4().hex[:10]}")
    node_id: str
    title: str
    type: Literal["raw", "normalized", "draft", "review", "publish_log", "feedback"]
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)


class AgentEvent(BaseModel):
    id: str = Field(default_factory=lambda: f"evt-{uuid4().hex[:10]}")
    run_id: str
    type: AgentEventType
    node_id: str | None = None
    title: str
    message: str
    created_at: str = Field(default_factory=now_iso)
    payload: dict[str, Any] = Field(default_factory=dict)


class AgentRun(BaseModel):
    id: str = Field(default_factory=lambda: f"run-{uuid4().hex[:10]}")
    agent_id: str
    graph_id: str
    status: RunStatus = RunStatus.idle
    current_node_id: str = "collect_source"
    started_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    heartbeat_at: str | None = None
    heartbeat_count: int = 0
    retry_count: int = 0
    parent_run_id: str | None = None
    failed_reason: str | None = None
    pending_human_actions: list[HumanDecision] = Field(default_factory=list)
    artifacts: list[RunArtifact] = Field(default_factory=list)
    events: list[AgentEvent] = Field(default_factory=list)
    state: dict[str, Any] = Field(default_factory=dict)


class StartRunRequest(BaseModel):
    agent_id: str = "content-operator"
    topic: str = "demo topic"
    sources: list[str] = Field(default_factory=list)
    auto_approve: bool = False
    parent_run_id: str | None = None
    retry_count: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunHeartbeatRequest(BaseModel):
    node_id: str | None = None
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunFailRequest(BaseModel):
    reason: str


class RunRecoveryRequest(BaseModel):
    now: str | None = None
    stale_after_seconds: int = 900
    limit: int = 100
    reason: str | None = None
    auto_retry: bool = False
    max_retry_count: int = 1
    auto_approve_retry: bool = False


class RunRetryRequest(BaseModel):
    note: str | None = None
    reset_to_node: str = "collect_source"
    auto_approve: bool = False


class ScheduledJobRequest(BaseModel):
    name: str
    agent_id: str = "content-operator"
    graph_id: str = "agent-production-loop"
    trigger: TriggerKind = TriggerKind.manual
    schedule: str | None = None
    topic: str = "scheduled topic"
    sources: list[str] = Field(default_factory=list)
    auto_approve: bool = False
    enabled: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ScheduledJob(BaseModel):
    id: str = Field(default_factory=lambda: f"job-{uuid4().hex[:10]}")
    name: str
    agent_id: str
    graph_id: str
    trigger: TriggerKind
    schedule: str | None = None
    status: ScheduledJobStatus = ScheduledJobStatus.active
    topic: str
    sources: list[str] = Field(default_factory=list)
    auto_approve: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    last_run_id: str | None = None
    last_run_at: str | None = None
    run_count: int = 0


class ScheduledJobDecisionRequest(BaseModel):
    status: ScheduledJobStatus


class SchedulerScanRequest(BaseModel):
    now: str | None = None
    limit: int = 20


class EventTriggerRequest(BaseModel):
    event_type: str
    payload: dict[str, Any] = Field(default_factory=dict)
    limit: int = 20


class HumanDecisionRequest(BaseModel):
    decision: HumanDecision
    note: str | None = None
    edited_payload: dict[str, Any] = Field(default_factory=dict)


class HumanGateReviewRequest(BaseModel):
    decision: HumanDecision
    note: str | None = None
    score: int | None = None
    edited_payload: dict[str, Any] = Field(default_factory=dict)
    resolved_by: str = "manual"


class HumanGateReview(BaseModel):
    id: str = Field(default_factory=lambda: f"gate-{uuid4().hex[:10]}")
    run_id: str
    node_id: str
    status: HumanGateStatus = HumanGateStatus.pending
    allowed_decisions: list[HumanDecision] = Field(default_factory=list)
    requested_by: str = "runtime"
    created_at: str = Field(default_factory=now_iso)
    updated_at: str = Field(default_factory=now_iso)
    decision: HumanDecision | None = None
    note: str | None = None
    score: int | None = None
    edited_payload: dict[str, Any] = Field(default_factory=dict)
    resolved_by: str | None = None
    resolved_at: str | None = None
