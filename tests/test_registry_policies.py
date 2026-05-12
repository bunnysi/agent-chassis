from agentgraph_core.models import KnowledgeDecisionRequest, ToolDefinition, ToolExecutionRequest, ToolRisk
from agentgraph_core.tool_registry import ToolRegistry
from agentgraph_core.knowledge_ledger import KnowledgeLedger
from agentgraph_core.models import KnowledgeRecordRequest


def test_tool_registry_has_no_default_demo_tools():
    registry = ToolRegistry()
    assert registry.list_tools() == []


def test_tool_registry_executes_explicit_handler():
    registry = ToolRegistry(
        tools=[ToolDefinition(id='echo', name='Echo', description='Echo input', risk=ToolRisk.read)],
        handlers={'echo': lambda payload: {'echo': payload}},
    )
    execution = registry.create_execution(ToolExecutionRequest(tool_id='echo', input={'hello': 'world'}))
    assert execution.status.value == 'succeeded'
    assert execution.output == {'echo': {'hello': 'world'}}


def test_knowledge_ledger_has_no_default_seed_records():
    assert KnowledgeLedger().seed_records() == []


def test_knowledge_candidate_promotes_with_real_request_model():
    ledger = KnowledgeLedger()
    record, evidence = ledger.create_candidate(KnowledgeRecordRequest(
        subject='subject',
        summary='summary',
        source='test',
        confidence=0.8,
        evidence=[
            {'source': 'a', 'quote': 'one', 'confidence': 0.8},
            {'source': 'b', 'quote': 'two', 'confidence': 0.82},
        ],
    ))
    record.evidence_count = len(evidence)
    promoted = ledger.apply_decision(record, KnowledgeDecisionRequest(decision='promote'))
    assert promoted.status.value == 'stable'
