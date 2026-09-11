from agent_chassis import (
    AgentRun,
    HumanDecision,
    HumanGateRegistry,
    KnowledgeLedger,
    KnowledgeRecordRequest,
    RunStatus,
    SQLiteStore,
)


def test_store_roundtrip_run(tmp_path):
    store = SQLiteStore(tmp_path / 'agent-chassis.sqlite3')
    run = AgentRun(agent_id='agent', graph_id='graph', status=RunStatus.running)
    store.save_run(run)
    loaded = store.get_run(run.id)
    assert loaded is not None
    assert loaded.id == run.id
    assert loaded.status == RunStatus.running


def test_human_gate_created_for_waiting_run():
    run = AgentRun(agent_id='agent', graph_id='graph', status=RunStatus.waiting_for_human, current_node_id='review')
    run.pending_human_actions = [HumanDecision.approve, HumanDecision.reject]
    gate = HumanGateRegistry().create_for_run(run)
    assert gate is not None
    assert gate.node_id == 'review'
    assert HumanDecision.approve in gate.allowed_decisions


def test_knowledge_candidate_promotes_with_policy():
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
    promoted = ledger.apply_decision(record, type('Req', (), {'decision': 'promote', 'note': None, 'summary': None, 'confidence': None})())
    assert promoted.status.value == 'stable'
