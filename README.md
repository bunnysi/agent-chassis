# AgentGraph Core

可复用的 Python 运行时原语，用于构建**可观察、人在回路**的 Agent 系统：透明的运行生命周期、工具审计、人工审批门、产物跟踪、知识晋升与 SQLite 持久化。

应用层保留自己的 UI、领域模型与存储权威；Core 只提供运行控制面和可观察性契约。

## 模块

| 模块 | 职责 |
|---|---|
| `models` | 全部领域模型（Agent/Run/Graph/Tool/Event/Artifact/Gate/Knowledge/Job） |
| `graph_registry` | 把声明的 GraphDefinition（节点/边/条件路由）编译成 LangGraph 运行时 |
| `tool_registry` | 工具注册、启用/停用、风险分级（read/write/publish）、审批门、执行状态 |
| `human_gate` | 人工审批门标准契约（approve/reject/edit/score/need_more_data） |
| `knowledge_ledger` | 知识候选 → 稳定 → 拒绝 账本（晋升需 confidence≥0.78 且 evidence≥2） |
| `scheduler` | manual/cron/event 触发的最小调度层（cron 支持 `*`、`*/N`、精确值） |
| `store` | SQLite 持久化（WAL）：run 全量 JSON 快照 + 事件/产物/决策等查询表镜像 |

不包含：前端、业务领域模型、应用自身的存储方案。运行时节点/路由 handler 由应用提供（v0 用代码注册），图拓扑与入口从定义读取。

## 安装

```bash
pip install -e '.[test]'   # Python >=3.11, 依赖 pydantic>=2, langgraph>=0.2
```

## 图运行时

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

## 工具注册

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

被停用或需要审批（`requires_approval` 且未 `auto_approve`）的工具会被标记为 `blocked`。

## 持久化

默认 SQLite 路径 `data/agentgraph.sqlite3`，可用环境变量覆盖：

```bash
AGENTGRAPH_DB_PATH=/path/to/agentgraph.sqlite3
```

## 测试

```bash
pytest -q
```