# AgentGraph Core

AgentGraph Core is the reusable runtime foundation extracted from `nophp/bot`.

It is intentionally **not** a product UI. It provides the shared backend primitives that projects like Bot Workshop, DotNovel, SOVPS, Fenhei, and Diana-bot can build on while keeping their own product-specific interfaces.

## What it includes

- Agent registry models: `AgentProfile`
- Graph registry models: `GraphDefinition`, `GraphNode`, `GraphEdge`
- Tool registry and execution records: `ToolDefinition`, `ToolExecution`
- Run lifecycle: `AgentRun`, `RunStatus`, heartbeat, retry/failure metadata
- Event stream: `AgentEvent`
- Artifact index: `RunArtifact`
- Human review gates: `HumanGateReview`
- Knowledge ledger: candidate / stable / rejected records with evidence
- Schedule model: manual / cron / event triggers
- SQLite persistence: `SQLiteStore`
- LangGraph adapter: `build_runtime_graph(...)`

## What it deliberately excludes

- No Bot Workshop frontend
- No DotNovel/SOVPS/Fenhei domain models
- No product-specific UI assumptions
- No requirement to replace a project's existing file authority or database

## Architecture

```text
Project UI / API adapter
  -> AgentGraph Core
      -> AgentProfile / GraphDefinition / ToolDefinition
      -> AgentRun / AgentEvent / RunArtifact
      -> HumanGateReview
      -> KnowledgeRecord / KnowledgeEvidence
      -> ScheduledJob
  -> Project-specific tools and state authority
```

## Minimal graph example

```python
from agentgraph_core import AgentRun, GraphRuntimeSpec, RunStatus, build_runtime_graph, default_entry_node
from agentgraph_core.demo_catalog import GRAPH
from examples.demo_runtime import NODE_HANDLERS, ROUTE_HANDLERS

spec = GraphRuntimeSpec(
    definition=GRAPH,
    entry_node_id=default_entry_node(GRAPH),
    node_handlers=NODE_HANDLERS,
    route_handlers=ROUTE_HANDLERS,
)
compiled = build_runtime_graph(spec)
result = compiled.invoke({
    "payload": {
        "run": AgentRun(agent_id="content-operator", graph_id=GRAPH.id, status=RunStatus.running),
        "topic": "demo",
        "sources": ["demo://source"],
        "auto_approve": True,
    }
})
```

## Persistence

By default SQLite uses:

```text
data/agentgraph.sqlite3
```

Override with:

```bash
AGENTGRAPH_DB_PATH=/path/to/agentgraph.sqlite3
```

## Development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## Intended use

- `nophp/bot`: keeps the generic Workshop UI and reference implementation.
- DotNovel: keeps novel workbench UI and file authority, uses AgentGraph Core for run/event/artifact/human-gate/knowledge plumbing.
- SOVPS: uses candidate/stable evidence ledger and scheduled agent runs.
- Fenhei/Diana: can selectively reuse run/event/tool/human-gate primitives.
