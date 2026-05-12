from __future__ import annotations

from typing import Callable

from .models import ToolDefinition, ToolDefinitionRequest, ToolExecution, ToolExecutionRequest, ToolExecutionStatus, ToolRisk, now_iso

ToolHandler = Callable[[dict], dict]


class ToolRegistry:
    """Tool definition and execution policy registry.

    Tools and handlers are explicit constructor inputs. Projects can provide their
    own domain tools while reusing approval, enabled/disabled, execution status,
    and persistence behavior from the core package.
    """

    def __init__(self, tools: list[ToolDefinition] | None = None, handlers: dict[str, ToolHandler] | None = None, store=None):
        persisted_tools = store.list_tool_definitions() if store else []
        self._store = store
        self._tools = {tool.id: tool for tool in (tools or [])}
        self._tools.update({tool.id: tool for tool in persisted_tools})
        self._handlers = handlers or {}

    def list_tools(self) -> list[ToolDefinition]:
        return list(self._tools.values())

    def get_tool(self, tool_id: str) -> ToolDefinition | None:
        return self._tools.get(tool_id)

    def register_handler(self, tool_id: str, handler: ToolHandler) -> None:
        self._handlers[tool_id] = handler

    def upsert_tool(self, request: ToolDefinitionRequest) -> ToolDefinition:
        tool_id = request.id or f"tool-{now_iso().replace(':', '').replace('+', '-')}"
        previous = self._tools.get(tool_id)
        metadata = dict(request.metadata)
        metadata.setdefault("updated_at", now_iso())
        if previous:
            metadata.setdefault("created_at", previous.metadata.get("created_at", previous.metadata.get("updated_at")))
        else:
            metadata.setdefault("created_at", metadata["updated_at"])
        tool = ToolDefinition(
            id=tool_id,
            name=request.name,
            description=request.description,
            input_schema=request.input_schema,
            risk=request.risk,
            requires_approval=request.requires_approval,
            enabled=request.enabled,
            command=request.command,
            adapter=request.adapter,
            timeout_seconds=request.timeout_seconds,
            tags=request.tags,
            version=request.version or (previous.version + 1 if previous else 1),
            metadata=metadata,
        )
        self._tools[tool.id] = tool
        if self._store:
            self._store.save_tool_definition(tool)
        return tool

    def set_enabled(self, tool_id: str, enabled: bool) -> ToolDefinition:
        tool = self.get_tool(tool_id)
        if not tool:
            raise ValueError("tool not found")
        tool.enabled = enabled
        tool.metadata = {**tool.metadata, "updated_at": now_iso()}
        if self._store:
            self._store.save_tool_definition(tool)
        return tool

    def create_execution(self, request: ToolExecutionRequest) -> ToolExecution:
        tool = self.get_tool(request.tool_id)
        if not tool:
            raise ValueError("tool not found")
        execution = ToolExecution(
            tool_id=tool.id,
            run_id=request.run_id,
            node_id=request.node_id,
            risk=tool.risk,
            requires_approval=tool.requires_approval,
            input=request.input,
            requested_by=request.requested_by,
        )
        if not tool.enabled:
            execution.status = ToolExecutionStatus.blocked
            execution.error = "tool disabled"
        elif tool.requires_approval and not request.auto_approve:
            execution.status = ToolExecutionStatus.blocked
            execution.error = "approval required"
        else:
            self.run_execution(execution)
        execution.updated_at = now_iso()
        if self._store:
            self._store.save_tool_execution(execution)
        return execution

    def run_execution(self, execution: ToolExecution) -> ToolExecution:
        tool = self.get_tool(execution.tool_id)
        if not tool:
            execution.status = ToolExecutionStatus.failed
            execution.error = "tool not found"
            execution.updated_at = now_iso()
            return execution
        if tool.requires_approval and execution.risk == ToolRisk.publish and execution.status == ToolExecutionStatus.blocked:
            execution.error = "approval required"
            execution.updated_at = now_iso()
            return execution
        handler = self._handlers.get(tool.id)
        if not handler:
            execution.status = ToolExecutionStatus.failed
            execution.error = "handler not registered"
            execution.updated_at = now_iso()
            return execution
        try:
            execution.status = ToolExecutionStatus.running
            execution.output = handler(execution.input)
            execution.status = ToolExecutionStatus.succeeded
            execution.error = None
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            execution.status = ToolExecutionStatus.failed
            execution.error = str(exc)
        execution.updated_at = now_iso()
        if self._store:
            self._store.save_tool_execution(execution)
        return execution
