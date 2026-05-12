from __future__ import annotations

from agentgraph_core.models import ToolDefinition, ToolRisk


def fetch_sources(payload: dict) -> dict:
    sources = payload.get("sources") or ["demo://source"]
    return {"sources": sources, "count": len(sources), "summary": f"Fetched {len(sources)} source(s)."}


def extract_facts(payload: dict) -> dict:
    return {
        "candidate_facts": [
            {
                "subject": payload.get("subject") or "demo subject",
                "summary": "Candidate fact extracted by demo tool.",
                "confidence": 0.62,
                "source_count": 1,
            }
        ]
    }


def generate_draft(payload: dict) -> dict:
    topic = payload.get("topic") or "demo topic"
    return {"title": f"Draft: {topic}", "status": "draft", "sections": ["context", "evidence", "next action"]}


def publish(payload: dict) -> dict:
    return {"published": True, "target": payload.get("target") or "demo://publish", "artifact_id": payload.get("artifact_id")}


DEMO_TOOLS = [
    ToolDefinition(
        id="crawler.fetch_sources",
        name="Fetch sources",
        description="Demo source collection tool.",
        risk=ToolRisk.read,
        tags=["demo", "source"],
    ),
    ToolDefinition(
        id="knowledge.extract_facts",
        name="Extract facts",
        description="Demo fact extraction tool.",
        risk=ToolRisk.write,
        tags=["demo", "knowledge"],
    ),
    ToolDefinition(
        id="draft.generate",
        name="Generate draft",
        description="Demo draft generation tool.",
        risk=ToolRisk.write,
        tags=["demo", "draft"],
    ),
    ToolDefinition(
        id="publisher.publish",
        name="Publish",
        description="Demo publish tool that requires approval.",
        risk=ToolRisk.publish,
        requires_approval=True,
        tags=["demo", "publish"],
    ),
]

DEMO_HANDLERS = {
    "crawler.fetch_sources": fetch_sources,
    "knowledge.extract_facts": extract_facts,
    "draft.generate": generate_draft,
    "publisher.publish": publish,
}
