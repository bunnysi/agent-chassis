# AgentGraph Core

AgentGraph Core is the reusable runtime foundation extracted from `nophp/bot`.

It is intentionally **not** a product UI. It provides shared backend primitives for projects that need transparent agent execution, human review, tool auditing, scheduled runs, and evidence-based knowledge promotion.

## Core idea

```text
project UI / API adapter
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
  -> project-specific tools and state authority
```

Projects keep their own product shape. DotNovel can stay a novel workbench, SOVPS can stay a data/content site, Fenhei can stay a mobile companion app. They reuse the runtime contract, not a forced admin UI.

## Included

- `AgentProfile`: agent identity, responsibility, model, knowledge boundary.
- `GraphDefinition`: product-visible nodes, edges, and conditional routing contract.
- `ToolDefinition` / `ToolExecution`: tool registry, enable/disable, risk, approval, execution status.
- `AgentRun`: lifecycle, current node, heartbeat, retry/failure metadata.
- `AgentEvent`: frontend-visible event stream.
- `RunArtifact`: index for generated artifacts without forcing large payloads into SQLite.
- `HumanGateReview`: approve / reject / edit / score / need-more-data gate.
- `KnowledgeRecord` / `KnowledgeEvidence`: candidate -> stable -> rejected ledger.
- `ScheduledJob`: manual / cron / event trigger model.
- `SQLiteStore`: small deployable persistence layer.
- `build_runtime_graph(...)`: LangGraph adapter for registered graph definitions.

## Excluded

- No Bot Workshop frontend.
- No DotNovel / SOVPS / Fenhei domain models.
- No product-specific UI assumptions.
- No requirement to replace a project's existing file authority or database.

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

## Project integration pattern

### Bot Workshop

Bot keeps the generic Workshop UI and uses AgentGraph Core as its runtime foundation.

### DotNovel

DotNovel should keep its novel workbench UI and file authority:

```text
DotNovel UI
  -> DotNovel API adapter
  -> agentgraph-core run/event/artifact/human-gate/knowledge layer
  -> Novel runtime tools
  -> novels/<id>/ files + Honcho memory
```

### SOVPS

SOVPS can reuse scheduled runs, tool execution logs, and candidate/stable knowledge promotion for vendor, line, IP, evidence, and article workflows.

## Development checks

```bash
pytest -q
python -m compileall agentgraph_core examples tests
```
