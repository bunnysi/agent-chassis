from examples.catalog.demo_catalog import GRAPH
from agentgraph_core.graph_registry import GraphRuntimeSpec, build_runtime_graph, default_entry_node
from agentgraph_core.models import AgentRun, RunStatus
from examples.demo_runtime import NODE_HANDLERS, ROUTE_HANDLERS


def test_graph_registry_compiles_from_definition():
    spec = GraphRuntimeSpec(
        definition=GRAPH,
        entry_node_id=default_entry_node(GRAPH),
        node_handlers=NODE_HANDLERS,
        route_handlers=ROUTE_HANDLERS,
    )
    compiled = build_runtime_graph(spec)
    result = compiled.invoke(
        {
            'payload': {
                'run': AgentRun(
                    agent_id='content-operator',
                    graph_id=GRAPH.id,
                    status=RunStatus.running,
                ),
                'topic': 'registry compile',
                'sources': ['demo://registry'],
                'auto_approve': True,
            }
        },
        {'recursion_limit': 25},
    )
    assert result['payload']['run'].graph_id == GRAPH.id
    assert result['payload']['run'].status.value == 'completed'


def test_graph_registry_requires_handlers():
    spec = GraphRuntimeSpec(
        definition=GRAPH,
        entry_node_id=default_entry_node(GRAPH),
        node_handlers={},
        route_handlers={},
    )
    try:
        build_runtime_graph(spec)
    except ValueError as exc:
        assert 'missing node handlers' in str(exc)
    else:
        raise AssertionError('missing handlers should fail')
