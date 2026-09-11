# agent-chassis

A sketch of a chassis for human-in-the-loop agents: graph runs, tool policy, approval gates, a knowledge ledger, and SQLite snapshots.

This is a **design experiment**. The code is a small set of Python primitives, not a product you should build on.

## What it sketches

| Piece | Idea |
|---|---|
| `models` | Agents, runs, graphs, tools, events, artifacts, gates, knowledge, jobs |
| `graph_registry` | Compile a declared graph (nodes / edges / routes) to LangGraph |
| `tool_registry` | Register tools, risk (`read` / `write` / `publish`), enable/disable, approval |
| `human_gate` | Standard review: approve, reject, edit, score, need more data |
| `knowledge_ledger` | Candidate → stable / rejected (promote needs confidence ≥ 0.78 and ≥ 2 evidence) |
| `scheduler` | Manual / cron / event. Cron is `*`, `*/N`, or an exact field |
| `store` | SQLite WAL: full run JSON plus query tables |

The application still owns UI, domain models, and real storage. Node and route handlers stay in app code.

## Quick start

```bash
git clone https://github.com/hareai/agent-chassis.git
cd agent-chassis
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[test]'
pytest -q
```

Python ≥ 3.11. Depends on `pydantic>=2` and `langgraph>=0.2`.

## Usage

```python
from agent_chassis import ToolRegistry
from agent_chassis.models import ToolDefinition, ToolRisk, ToolExecutionRequest

registry = ToolRegistry(
    tools=[ToolDefinition(id="echo", name="Echo", description="Echo input", risk=ToolRisk.read)],
    handlers={"echo": lambda payload: {"echo": payload}},
)
execution = registry.create_execution(
    ToolExecutionRequest(tool_id="echo", input={"hello": "world"})
)
```

A graph compile + invoke lives in `examples/`.

SQLite default path is `data/agent-chassis.sqlite3`. Override with `AGENT_CHASSIS_DB_PATH`.

## License

[MIT](LICENSE)
