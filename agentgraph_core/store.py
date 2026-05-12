from __future__ import annotations

import json
import os
import sqlite3
from pathlib import Path
from threading import RLock
from typing import Iterable

from .models import AgentEvent, AgentProfile, AgentRun, GraphDefinition, HumanDecision, HumanGateReview, HumanGateStatus, KnowledgeEvidence, KnowledgeRecord, KnowledgeStatus, RunArtifact, ScheduledJob, ScheduledJobStatus, ToolDefinition, ToolExecution, now_iso

DEFAULT_DB_PATH = Path(os.getenv("AGENTGRAPH_DB_PATH", "data/agentgraph.sqlite3"))


class SQLiteStore:
    """SQLite persistence layer for AgentGraph runtime state.

    Stores the full run JSON snapshot so the LangGraph runtime can evolve quickly
    without premature relational schema churn. It also mirrors events, artifacts,
    and human decisions into query tables for visible admin pages.
    """

    def __init__(self, path: str | Path = DEFAULT_DB_PATH):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_column(self, conn: sqlite3.Connection, table: str, column: str, ddl: str) -> None:
        existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if column not in existing:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")

    def _init_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    agent_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    current_node_id TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    heartbeat_at TEXT,
                    heartbeat_count INTEGER NOT NULL DEFAULT 0,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    parent_run_id TEXT,
                    failed_reason TEXT,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_updated_at ON runs(updated_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_status ON runs(status)")
            self._ensure_column(conn, "runs", "heartbeat_at", "TEXT")
            self._ensure_column(conn, "runs", "heartbeat_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "runs", "retry_count", "INTEGER NOT NULL DEFAULT 0")
            self._ensure_column(conn, "runs", "parent_run_id", "TEXT")
            self._ensure_column(conn, "runs", "failed_reason", "TEXT")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_heartbeat_at ON runs(heartbeat_at DESC)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_runs_parent ON runs(parent_run_id)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    type TEXT NOT NULL,
                    node_id TEXT,
                    title TEXT NOT NULL,
                    message TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_run_created ON events(run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON events(type)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS artifacts (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    type TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_run_created ON artifacts(run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_artifacts_type ON artifacts(type)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS human_decisions (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    decision TEXT NOT NULL,
                    node_id TEXT,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_human_decisions_run_created ON human_decisions(run_id, created_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS human_gate_reviews (
                    id TEXT PRIMARY KEY,
                    run_id TEXT NOT NULL,
                    node_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    allowed_decisions_json TEXT NOT NULL,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    decision TEXT,
                    note TEXT,
                    score INTEGER,
                    resolved_by TEXT,
                    resolved_at TEXT,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_human_gate_reviews_run_created ON human_gate_reviews(run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_human_gate_reviews_status ON human_gate_reviews(status)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS tool_executions (
                    id TEXT PRIMARY KEY,
                    tool_id TEXT NOT NULL,
                    run_id TEXT,
                    node_id TEXT,
                    status TEXT NOT NULL,
                    risk TEXT NOT NULL,
                    requires_approval INTEGER NOT NULL,
                    input_json TEXT NOT NULL,
                    output_json TEXT NOT NULL,
                    error TEXT,
                    requested_by TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_tool_created ON tool_executions(tool_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_run_created ON tool_executions(run_id, created_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_tool_executions_status ON tool_executions(status)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_records (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    summary TEXT NOT NULL,
                    evidence_count INTEGER NOT NULL,
                    confidence REAL NOT NULL,
                    source TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    promoted_at TEXT,
                    rejected_at TEXT,
                    correction_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_status ON knowledge_records(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_subject ON knowledge_records(subject)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_confidence ON knowledge_records(confidence)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS knowledge_evidence (
                    id TEXT PRIMARY KEY,
                    knowledge_id TEXT NOT NULL,
                    source TEXT NOT NULL,
                    quote TEXT NOT NULL,
                    url TEXT,
                    confidence REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    FOREIGN KEY(knowledge_id) REFERENCES knowledge_records(id) ON DELETE CASCADE
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_evidence_record ON knowledge_evidence(knowledge_id, created_at)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS scheduled_jobs (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    agent_id TEXT NOT NULL,
                    graph_id TEXT NOT NULL,
                    trigger TEXT NOT NULL,
                    schedule TEXT,
                    status TEXT NOT NULL,
                    topic TEXT NOT NULL,
                    auto_approve INTEGER NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_run_id TEXT,
                    last_run_at TEXT,
                    run_count INTEGER NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_status ON scheduled_jobs(status)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_scheduled_jobs_trigger ON scheduled_jobs(trigger)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registry_agents (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_agents_status ON registry_agents(status)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registry_graphs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_graphs_status ON registry_graphs(status)")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS registry_tools (
                    id TEXT PRIMARY KEY,
                    enabled INTEGER NOT NULL,
                    version INTEGER NOT NULL,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_registry_tools_enabled ON registry_tools(enabled)")
            conn.commit()

    def save_run(self, run: AgentRun) -> AgentRun:
        run.updated_at = run.updated_at or now_iso()
        payload = run.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                """
                INSERT INTO runs (
                    id, agent_id, graph_id, status, current_node_id,
                    started_at, updated_at, heartbeat_at, heartbeat_count,
                    retry_count, parent_run_id, failed_reason, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    agent_id=excluded.agent_id,
                    graph_id=excluded.graph_id,
                    status=excluded.status,
                    current_node_id=excluded.current_node_id,
                    started_at=excluded.started_at,
                    updated_at=excluded.updated_at,
                    heartbeat_at=excluded.heartbeat_at,
                    heartbeat_count=excluded.heartbeat_count,
                    retry_count=excluded.retry_count,
                    parent_run_id=excluded.parent_run_id,
                    failed_reason=excluded.failed_reason,
                    payload_json=excluded.payload_json
                """,
                (
                    run.id,
                    run.agent_id,
                    run.graph_id,
                    run.status.value,
                    run.current_node_id,
                    run.started_at,
                    run.updated_at,
                    run.heartbeat_at,
                    run.heartbeat_count,
                    run.retry_count,
                    run.parent_run_id,
                    run.failed_reason,
                    payload,
                ),
            )
            self._replace_events(conn, run)
            self._replace_artifacts(conn, run)
            self._replace_human_decisions(conn, run)
            conn.commit()
        return run

    def _replace_events(self, conn: sqlite3.Connection, run: AgentRun) -> None:
        conn.execute("DELETE FROM events WHERE run_id = ?", (run.id,))
        conn.executemany(
            """
            INSERT INTO events (id, run_id, type, node_id, title, message, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    event.id,
                    run.id,
                    event.type.value,
                    event.node_id,
                    event.title,
                    event.message,
                    event.created_at,
                    json.dumps(event.payload, ensure_ascii=False),
                )
                for event in run.events
            ],
        )

    def _replace_artifacts(self, conn: sqlite3.Connection, run: AgentRun) -> None:
        conn.execute("DELETE FROM artifacts WHERE run_id = ?", (run.id,))
        conn.executemany(
            """
            INSERT INTO artifacts (id, run_id, node_id, title, type, summary, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            [
                (
                    artifact.id,
                    run.id,
                    artifact.node_id,
                    artifact.title,
                    artifact.type,
                    artifact.summary,
                    artifact.created_at,
                    json.dumps(artifact.payload, ensure_ascii=False),
                )
                for artifact in run.artifacts
            ],
        )

    def _replace_human_decisions(self, conn: sqlite3.Connection, run: AgentRun) -> None:
        conn.execute("DELETE FROM human_decisions WHERE run_id = ?", (run.id,))
        rows = []
        for event in run.events:
            if event.type.value != "human_decision":
                continue
            decision = _decision_from_event(event)
            rows.append(
                (
                    event.id,
                    run.id,
                    decision,
                    event.node_id,
                    event.message,
                    event.created_at,
                    json.dumps(event.payload, ensure_ascii=False),
                )
            )
        conn.executemany(
            """
            INSERT INTO human_decisions (id, run_id, decision, node_id, note, created_at, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            rows,
        )

    def get_run(self, run_id: str) -> AgentRun | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            return None
        return AgentRun.model_validate_json(row["payload_json"])

    def list_runs(self, limit: int = 100) -> list[AgentRun]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM runs ORDER BY updated_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [AgentRun.model_validate_json(row["payload_json"]) for row in rows]

    def list_events(self, run_id: str) -> list[AgentEvent]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM events WHERE run_id = ? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
        return [
            AgentEvent(
                id=row["id"],
                run_id=row["run_id"],
                type=row["type"],
                node_id=row["node_id"],
                title=row["title"],
                message=row["message"],
                created_at=row["created_at"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    def list_artifacts(self, run_id: str) -> list[RunArtifact]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM artifacts WHERE run_id = ? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
        return [
            RunArtifact(
                id=row["id"],
                node_id=row["node_id"],
                title=row["title"],
                type=row["type"],
                summary=row["summary"],
                created_at=row["created_at"],
                payload=json.loads(row["payload_json"]),
            )
            for row in rows
        ]

    def list_human_decisions(self, run_id: str) -> list[dict[str, str | dict]]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM human_decisions WHERE run_id = ? ORDER BY created_at, id",
                (run_id,),
            ).fetchall()
        return [
            {
                "id": row["id"],
                "run_id": row["run_id"],
                "decision": row["decision"],
                "node_id": row["node_id"],
                "note": row["note"],
                "created_at": row["created_at"],
                "payload": json.loads(row["payload_json"]),
            }
            for row in rows
        ]

    def save_run_with_human_gate(self, run: AgentRun, review: HumanGateReview | None) -> AgentRun:
        self.save_run(run)
        if review:
            self.save_human_gate_review(review)
        return run

    def save_human_gate_review(self, review: HumanGateReview) -> HumanGateReview:
        review.updated_at = now_iso()
        payload = review.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO human_gate_reviews (
                    id, run_id, node_id, status, allowed_decisions_json, requested_by,
                    created_at, updated_at, decision, note, score, resolved_by, resolved_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    run_id=excluded.run_id,
                    node_id=excluded.node_id,
                    status=excluded.status,
                    allowed_decisions_json=excluded.allowed_decisions_json,
                    requested_by=excluded.requested_by,
                    updated_at=excluded.updated_at,
                    decision=excluded.decision,
                    note=excluded.note,
                    score=excluded.score,
                    resolved_by=excluded.resolved_by,
                    resolved_at=excluded.resolved_at,
                    payload_json=excluded.payload_json
                """,
                (
                    review.id,
                    review.run_id,
                    review.node_id,
                    review.status.value,
                    json.dumps([decision.value for decision in review.allowed_decisions], ensure_ascii=False),
                    review.requested_by,
                    review.created_at,
                    review.updated_at,
                    review.decision.value if review.decision else None,
                    review.note,
                    review.score,
                    review.resolved_by,
                    review.resolved_at,
                    payload,
                ),
            )
            conn.commit()
        return review

    def get_human_gate_review(self, review_id: str) -> HumanGateReview | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM human_gate_reviews WHERE id = ?", (review_id,)).fetchone()
        if not row:
            return None
        return HumanGateReview.model_validate_json(row["payload_json"])

    def get_pending_human_gate_review_for_run(self, run_id: str) -> HumanGateReview | None:
        with self._lock, self._connect() as conn:
            row = conn.execute(
                "SELECT payload_json FROM human_gate_reviews WHERE run_id = ? AND status = ? ORDER BY created_at DESC LIMIT 1",
                (run_id, HumanGateStatus.pending.value),
            ).fetchone()
        if not row:
            return None
        return HumanGateReview.model_validate_json(row["payload_json"])

    def list_human_gate_reviews(self, run_id: str | None = None, status: HumanGateStatus | None = None, limit: int = 100) -> list[HumanGateReview]:
        query = "SELECT payload_json FROM human_gate_reviews"
        filters: list[str] = []
        params: list[str | int] = []
        if run_id:
            filters.append("run_id = ?")
            params.append(run_id)
        if status:
            filters.append("status = ?")
            params.append(status.value)
        if filters:
            query += " WHERE " + " AND ".join(filters)
        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        with self._lock, self._connect() as conn:
            rows = conn.execute(query, params).fetchall()
        return [HumanGateReview.model_validate_json(row["payload_json"]) for row in rows]

    def save_tool_execution(self, execution: ToolExecution) -> ToolExecution:
        payload = execution.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO tool_executions (
                    id, tool_id, run_id, node_id, status, risk, requires_approval,
                    input_json, output_json, error, requested_by, created_at, updated_at, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    tool_id=excluded.tool_id,
                    run_id=excluded.run_id,
                    node_id=excluded.node_id,
                    status=excluded.status,
                    risk=excluded.risk,
                    requires_approval=excluded.requires_approval,
                    input_json=excluded.input_json,
                    output_json=excluded.output_json,
                    error=excluded.error,
                    requested_by=excluded.requested_by,
                    created_at=excluded.created_at,
                    updated_at=excluded.updated_at,
                    payload_json=excluded.payload_json
                """,
                (
                    execution.id,
                    execution.tool_id,
                    execution.run_id,
                    execution.node_id,
                    execution.status.value,
                    execution.risk.value,
                    1 if execution.requires_approval else 0,
                    json.dumps(execution.input, ensure_ascii=False),
                    json.dumps(execution.output, ensure_ascii=False),
                    execution.error,
                    execution.requested_by,
                    execution.created_at,
                    execution.updated_at,
                    payload,
                ),
            )
            conn.commit()
        return execution

    def get_tool_execution(self, execution_id: str) -> ToolExecution | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM tool_executions WHERE id = ?", (execution_id,)).fetchone()
        if not row:
            return None
        return ToolExecution.model_validate_json(row["payload_json"])

    def list_tool_executions(self, limit: int = 100, run_id: str | None = None) -> list[ToolExecution]:
        with self._lock, self._connect() as conn:
            if run_id:
                rows = conn.execute(
                    "SELECT payload_json FROM tool_executions WHERE run_id = ? ORDER BY created_at DESC LIMIT ?",
                    (run_id, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM tool_executions ORDER BY created_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [ToolExecution.model_validate_json(row["payload_json"]) for row in rows]

    def save_agent_profile(self, agent: AgentProfile) -> AgentProfile:
        payload = agent.model_dump_json()
        updated_at = agent.metadata.get("updated_at") or now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_agents (id, status, version, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    version=excluded.version,
                    updated_at=excluded.updated_at,
                    payload_json=excluded.payload_json
                """,
                (agent.id, agent.status.value, agent.version, updated_at, payload),
            )
            conn.commit()
        return agent

    def list_agent_profiles(self) -> list[AgentProfile]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM registry_agents ORDER BY id").fetchall()
        return [AgentProfile.model_validate_json(row["payload_json"]) for row in rows]

    def save_graph_definition(self, graph: GraphDefinition) -> GraphDefinition:
        payload = graph.model_dump_json(by_alias=True)
        updated_at = graph.metadata.get("updated_at") or now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_graphs (id, status, version, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    version=excluded.version,
                    updated_at=excluded.updated_at,
                    payload_json=excluded.payload_json
                """,
                (graph.id, graph.status.value, graph.version, updated_at, payload),
            )
            conn.commit()
        return graph

    def list_graph_definitions(self) -> list[GraphDefinition]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM registry_graphs ORDER BY id").fetchall()
        return [GraphDefinition.model_validate_json(row["payload_json"]) for row in rows]

    def save_tool_definition(self, tool: ToolDefinition) -> ToolDefinition:
        payload = tool.model_dump_json()
        updated_at = tool.metadata.get("updated_at") or now_iso()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO registry_tools (id, enabled, version, updated_at, payload_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    enabled=excluded.enabled,
                    version=excluded.version,
                    updated_at=excluded.updated_at,
                    payload_json=excluded.payload_json
                """,
                (tool.id, 1 if tool.enabled else 0, tool.version, updated_at, payload),
            )
            conn.commit()
        return tool

    def list_tool_definitions(self) -> list[ToolDefinition]:
        with self._lock, self._connect() as conn:
            rows = conn.execute("SELECT payload_json FROM registry_tools ORDER BY id").fetchall()
        return [ToolDefinition.model_validate_json(row["payload_json"]) for row in rows]

    def save_knowledge_record(self, record: KnowledgeRecord, evidence: list[KnowledgeEvidence] | None = None) -> KnowledgeRecord:
        record.evidence_count = len(evidence or []) or record.evidence_count
        record.updated_at = now_iso()
        payload = record.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute("PRAGMA foreign_keys=ON")
            conn.execute(
                """
                INSERT INTO knowledge_records (
                    id, status, subject, summary, evidence_count, confidence, source,
                    updated_at, promoted_at, rejected_at, correction_count, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    subject=excluded.subject,
                    summary=excluded.summary,
                    evidence_count=excluded.evidence_count,
                    confidence=excluded.confidence,
                    source=excluded.source,
                    updated_at=excluded.updated_at,
                    promoted_at=excluded.promoted_at,
                    rejected_at=excluded.rejected_at,
                    correction_count=excluded.correction_count,
                    payload_json=excluded.payload_json
                """,
                (
                    record.id,
                    record.status.value,
                    record.subject,
                    record.summary,
                    record.evidence_count,
                    record.confidence,
                    record.source,
                    record.updated_at,
                    record.promoted_at,
                    record.rejected_at,
                    record.correction_count,
                    payload,
                ),
            )
            if evidence is not None:
                conn.execute("DELETE FROM knowledge_evidence WHERE knowledge_id = ?", (record.id,))
                conn.executemany(
                    """
                    INSERT INTO knowledge_evidence (id, knowledge_id, source, quote, url, confidence, created_at, payload_json)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    [
                        (
                            item.id,
                            record.id,
                            item.source,
                            item.quote,
                            item.url,
                            item.confidence,
                            item.created_at,
                            item.model_dump_json(),
                        )
                        for item in evidence
                    ],
                )
            conn.commit()
        return record

    def get_knowledge_record(self, record_id: str) -> KnowledgeRecord | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM knowledge_records WHERE id = ?", (record_id,)).fetchone()
        if not row:
            return None
        return KnowledgeRecord.model_validate_json(row["payload_json"])

    def list_knowledge_records(self, status: KnowledgeStatus | None = None, limit: int = 100) -> list[KnowledgeRecord]:
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT payload_json FROM knowledge_records WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM knowledge_records ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [KnowledgeRecord.model_validate_json(row["payload_json"]) for row in rows]

    def list_knowledge_evidence(self, record_id: str) -> list[KnowledgeEvidence]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT payload_json FROM knowledge_evidence WHERE knowledge_id = ? ORDER BY created_at, id",
                (record_id,),
            ).fetchall()
        return [KnowledgeEvidence.model_validate_json(row["payload_json"]) for row in rows]

    def save_scheduled_job(self, job: ScheduledJob) -> ScheduledJob:
        job.updated_at = now_iso()
        payload = job.model_dump_json()
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                INSERT INTO scheduled_jobs (
                    id, name, agent_id, graph_id, trigger, schedule, status, topic,
                    auto_approve, created_at, updated_at, last_run_id, last_run_at,
                    run_count, payload_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    name=excluded.name,
                    agent_id=excluded.agent_id,
                    graph_id=excluded.graph_id,
                    trigger=excluded.trigger,
                    schedule=excluded.schedule,
                    status=excluded.status,
                    topic=excluded.topic,
                    auto_approve=excluded.auto_approve,
                    updated_at=excluded.updated_at,
                    last_run_id=excluded.last_run_id,
                    last_run_at=excluded.last_run_at,
                    run_count=excluded.run_count,
                    payload_json=excluded.payload_json
                """,
                (
                    job.id,
                    job.name,
                    job.agent_id,
                    job.graph_id,
                    job.trigger.value,
                    job.schedule,
                    job.status.value,
                    job.topic,
                    1 if job.auto_approve else 0,
                    job.created_at,
                    job.updated_at,
                    job.last_run_id,
                    job.last_run_at,
                    job.run_count,
                    payload,
                ),
            )
            conn.commit()
        return job

    def get_scheduled_job(self, job_id: str) -> ScheduledJob | None:
        with self._lock, self._connect() as conn:
            row = conn.execute("SELECT payload_json FROM scheduled_jobs WHERE id = ?", (job_id,)).fetchone()
        if not row:
            return None
        return ScheduledJob.model_validate_json(row["payload_json"])

    def list_scheduled_jobs(self, status: ScheduledJobStatus | None = None, limit: int = 100) -> list[ScheduledJob]:
        with self._lock, self._connect() as conn:
            if status:
                rows = conn.execute(
                    "SELECT payload_json FROM scheduled_jobs WHERE status = ? ORDER BY updated_at DESC LIMIT ?",
                    (status.value, limit),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT payload_json FROM scheduled_jobs ORDER BY updated_at DESC LIMIT ?",
                    (limit,),
                ).fetchall()
        return [ScheduledJob.model_validate_json(row["payload_json"]) for row in rows]

    def clear_runs(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute("DELETE FROM scheduled_jobs")
            conn.execute("DELETE FROM tool_executions")
            conn.execute("DELETE FROM human_gate_reviews")
            conn.execute("DELETE FROM human_decisions")
            conn.execute("DELETE FROM artifacts")
            conn.execute("DELETE FROM events")
            conn.execute("DELETE FROM runs")
            conn.commit()

    def seed_runs(self, runs: Iterable[AgentRun]) -> None:
        for run in runs:
            self.save_run(run)


def _decision_from_event(event: AgentEvent) -> str:
    if event.payload.get("decision"):
        return str(event.payload["decision"])
    prefix = "Human decision: "
    if event.title.startswith(prefix):
        return event.title.removeprefix(prefix)
    if event.title == "Auto approved":
        return HumanDecision.approve.value
    return "unknown"
