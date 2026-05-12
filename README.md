# AgentGraph Core

AgentGraph Core is a small Python runtime foundation for building observable, human-in-the-loop agent systems.

It provides shared backend primitives for projects that need transparent agent execution, tool auditing, scheduled runs, human review, artifact tracking, and evidence-based knowledge promotion.

## Core idea

```text
application UI / API adapter
  -> agentgraph-core
      -> agent profile
      -> graph definition
      -> tool registry
      -> run lifecycle
      -> event stream
      -> artifact index
      -> human gate
      -> schedule
      -> knowledge ledger
  -> application-specific tools and state authority
```

Applications keep their own product shape, domain models, and storage authority. AgentGraph Core provides the common runtime contract.

## Included

- `AgentProfile`: agent identity, responsibility, model, and knowledge boundary.
- `GraphDefinition`: product-visible nodes, edges, and conditional routing contract.
- `ToolDefinition` / `ToolExecution`: tool registry, enable/disable, risk, approval, and execution status.
- `AgentRun`: lifecycle, current node, heartbeat, retry, and failure metadata.
- `AgentEvent`: frontend-visible event stream.
- `RunArtifact`: index for generated artifacts without forcing large payloads into SQLite.
- `HumanGateReview`: approve / reject / edit / score / need-more-data gate.
- `KnowledgeRecord` / `KnowledgeEvidence`: candidate -> stable -> rejected ledger.
- `ScheduledJob`: manual / cron / event trigger model.
- `SQLiteStore`: small deployable persistence layer.
- `build_runtime_graph(...)`: LangGraph adapter for registered graph definitions.

## Excluded

- No frontend.
- No product-specific domain models.
- No product-specific terminology.
- No requirement to replace an application's existing file authority or database.

## Install for development

```bash
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

## Minimal graph

```python
from agentgraph_core import AgentRun, GraphRuntimeSpec, RunStatus, build_runtime_graph, default_entry_node
from examples.catalog.demo_catalog import GRAPH
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

## Tool registry example

```python
from agentgraph_core import ToolRegistry
from agentgraph_core.models import ToolDefinition, ToolRisk, ToolExecutionRequest

registry = ToolRegistry(
    tools=[ToolDefinition(id="echo", name="Echo", description="Echo input", risk=ToolRisk.read)],
    handlers={"echo": lambda payload: {"echo": payload}},
)
execution = registry.create_execution(ToolExecutionRequest(tool_id="echo", input={"hello": "world"}))
assert execution.status == "succeeded"
```

## Persistence

Default SQLite path:

```text
data/agentgraph.sqlite3
```

Override:

```bash
AGENTGRAPH_DB_PATH=/path/to/agentgraph.sqlite3
```

`SQLiteStore` stores the full run JSON snapshot and mirrors events, artifacts, human decisions, tool executions, knowledge, schedules, and registry definitions into queryable tables.

## Application integration pattern

```text
application UI
  -> application API adapter
  -> agentgraph-core run/event/artifact/human-gate/knowledge layer
  -> application-specific tools
  -> application-specific state authority
```

Typical integrations keep large generated content, domain state, or external records in their existing storage system, while using AgentGraph Core for operational visibility and control-plane state.

## Development checks

```bash
pytest -q
python -m compileall agentgraph_core examples tests
```
