from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from langgraph.graph import END, StateGraph

from .models import GraphDefinition, GraphEdge

RouteFn = Callable[[dict], str]
NodeFn = Callable[[dict], dict]


@dataclass(frozen=True)
class GraphRuntimeSpec:
    definition: GraphDefinition
    entry_node_id: str
    node_handlers: dict[str, NodeFn]
    route_handlers: dict[str, RouteFn]


def build_runtime_graph(spec: GraphRuntimeSpec):
    """Compile a LangGraph runtime from a registered GraphDefinition.

    GraphDefinition stays the product-visible contract. Handlers stay code for v0,
    but edge topology, entry node, and conditional routing are read from the
    definition so projects can register different flows without rewriting the
    runtime class.
    """

    _validate_spec(spec)
    graph = StateGraph(dict)

    for node in spec.definition.nodes:
        graph.add_node(node.id, _handler_for(node.id, spec.node_handlers[node.id]))

    graph.set_entry_point(spec.entry_node_id)

    for node_id, edges in _group_edges(spec.definition.edges).items():
        if len(edges) == 1 and not edges[0].condition:
            graph.add_edge(node_id, edges[0].to_node)
            continue
        graph.add_conditional_edges(node_id, _route_for(node_id, spec.route_handlers[node_id]))

    terminal_nodes = {node.id for node in spec.definition.nodes} - {edge.from_node for edge in spec.definition.edges}
    for node_id in terminal_nodes:
        graph.add_edge(node_id, END)

    return graph.compile()


def default_entry_node(definition: GraphDefinition) -> str:
    targets = {edge.to_node for edge in definition.edges}
    for node in definition.nodes:
        if node.id not in targets:
            return node.id
    return definition.nodes[0].id


def _group_edges(edges: list[GraphEdge]) -> dict[str, list[GraphEdge]]:
    grouped: dict[str, list[GraphEdge]] = {}
    for edge in edges:
        grouped.setdefault(edge.from_node, []).append(edge)
    return grouped


def _handler_for(node_id: str, handler: NodeFn) -> NodeFn:
    def run_node(state: dict) -> dict:
        payload: dict[str, Any] = state.get("payload") or state
        result = handler(payload)
        return {"payload": result}

    run_node.__name__ = f"run_{node_id}"
    return run_node


def _route_for(node_id: str, handler: RouteFn) -> RouteFn:
    def route(state: dict) -> str:
        payload: dict[str, Any] = state.get("payload") or state
        target = handler(payload)
        return END if target == "__end__" else target

    route.__name__ = f"route_after_{node_id}"
    return route


def _validate_spec(spec: GraphRuntimeSpec) -> None:
    node_ids = {node.id for node in spec.definition.nodes}
    if spec.entry_node_id not in node_ids:
        raise ValueError(f"entry node not in graph: {spec.entry_node_id}")

    missing_handlers = sorted(node_ids - set(spec.node_handlers))
    if missing_handlers:
        raise ValueError(f"missing node handlers: {', '.join(missing_handlers)}")

    for edge in spec.definition.edges:
        if edge.from_node not in node_ids:
            raise ValueError(f"edge from unknown node: {edge.from_node}")
        if edge.to_node not in node_ids:
            raise ValueError(f"edge to unknown node: {edge.to_node}")

    grouped = _group_edges(spec.definition.edges)
    for node_id, edges in grouped.items():
        if len(edges) > 1 or edges[0].condition:
            if node_id not in spec.route_handlers:
                raise ValueError(f"missing route handler for conditional node: {node_id}")
