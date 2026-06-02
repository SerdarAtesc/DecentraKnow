"""
Knowledge Graph service.
Extracts entities and relationships from content using LLM,
stores them persistently in Qdrant for graph visualization.
"""

import json
from uuid import uuid4
from app.services.llm_service import get_provider
from app.core.config import get_settings

settings = get_settings()

EXTRACTION_PROMPT = """Extract entities and relationships from the following text.
Return ONLY valid JSON in this exact format (no markdown, no explanation):
{"entities": [{"name": "EntityName", "type": "technology|organization|concept|person|protocol|token"}], "relations": [{"source": "EntityA", "target": "EntityB", "relation": "built_on|uses|part_of|created_by|competes_with|enables|funds"}]}

Rules:
- Extract 3-8 key entities
- Extract 2-6 relationships between entities
- Entity names should be concise (1-3 words)
- Only include relationships that are clearly stated or strongly implied
- If no meaningful entities found, return {"entities": [], "relations": []}"""

GRAPH_COLLECTION = "knowledge_graph"

_qdrant_client = None
_qdrant_connected = False
_memory_graph_store: list[dict] = []


def _get_qdrant():
    global _qdrant_client, _qdrant_connected
    if _qdrant_connected:
        return _qdrant_client

    try:
        from qdrant_client import QdrantClient
        from qdrant_client.models import VectorParams, Distance

        if settings.qdrant_url and settings.qdrant_api_key:
            client = QdrantClient(
                url=settings.qdrant_url,
                api_key=settings.qdrant_api_key,
                timeout=10,
            )
        else:
            client = QdrantClient(
                host=settings.qdrant_host,
                port=settings.qdrant_port,
                timeout=3,
            )

        collections = client.get_collections().collections
        exists = any(c.name == GRAPH_COLLECTION for c in collections)
        if not exists:
            client.create_collection(
                collection_name=GRAPH_COLLECTION,
                vectors_config=VectorParams(size=4, distance=Distance.COSINE),
            )

        _qdrant_client = client
        _qdrant_connected = True
        print(f"[GraphService] Connected to Qdrant, collection: {GRAPH_COLLECTION}")
        return client
    except Exception as e:
        print(f"[GraphService] Qdrant unavailable ({e}), using in-memory fallback")
        return None


def _save_graph_entry(entry: dict):
    """Persist a graph extraction result."""
    client = _get_qdrant()
    if client:
        from qdrant_client.models import PointStruct
        point_id = str(uuid4())
        client.upsert(
            collection_name=GRAPH_COLLECTION,
            points=[
                PointStruct(
                    id=point_id,
                    vector=[0.0, 0.0, 0.0, 0.0],
                    payload=entry,
                )
            ],
        )
    else:
        _memory_graph_store.append(entry)


def _load_all_graph_entries(limit: int = 500) -> list[dict]:
    """Load all graph entries from storage."""
    client = _get_qdrant()
    if client:
        results = client.scroll(
            collection_name=GRAPH_COLLECTION,
            limit=limit,
            with_payload=True,
        )
        return [point.payload for point in results[0]]
    return _memory_graph_store[:limit]


def _clear_graph_store():
    """Clear all graph entries (used during rebuild)."""
    global _memory_graph_store
    client = _get_qdrant()
    if client:
        from qdrant_client.models import VectorParams, Distance
        client.delete_collection(collection_name=GRAPH_COLLECTION)
        client.create_collection(
            collection_name=GRAPH_COLLECTION,
            vectors_config=VectorParams(size=4, distance=Distance.COSINE),
        )
    else:
        _memory_graph_store = []


async def extract_entities_and_relations(
    content: str, content_hash: str, title: str
) -> dict:
    llm = get_provider("openai")
    user_message = f"Text to analyze:\n\n{content[:2000]}"

    try:
        response = await llm.generate(EXTRACTION_PROMPT, user_message)

        response = response.strip()
        if response.startswith("```"):
            response = response.split("\n", 1)[1] if "\n" in response else response
            response = response.rsplit("```", 1)[0]

        data = json.loads(response)

        entities = data.get("entities", [])
        relations = data.get("relations", [])

        for entity in entities:
            entity["source_hash"] = content_hash
            entity["source_title"] = title

        for relation in relations:
            relation["source_hash"] = content_hash
            relation["source_title"] = title

        graph_entry = {
            "content_hash": content_hash,
            "title": title,
            "entities": entities,
            "relations": relations,
        }
        _save_graph_entry(graph_entry)

        return graph_entry

    except (json.JSONDecodeError, KeyError, Exception) as e:
        print(f"[GraphService] Extraction failed for '{title}': {e}")
        return {"content_hash": content_hash, "title": title, "entities": [], "relations": []}


def get_graph(limit: int = 200, entity_type: str | None = None) -> dict:
    entries = _load_all_graph_entries(limit)

    all_entities = []
    all_relations = []
    seen_entities = set()

    for entry in entries:
        for entity in entry.get("entities", []):
            if entity_type and entity.get("type") != entity_type:
                continue
            key = entity["name"].lower()
            if key not in seen_entities:
                seen_entities.add(key)
                all_entities.append(entity)

        for relation in entry.get("relations", []):
            if entity_type:
                src = relation.get("source", "").lower()
                tgt = relation.get("target", "").lower()
                if src not in seen_entities and tgt not in seen_entities:
                    continue
            all_relations.append(relation)

    nodes = [
        {
            "id": e["name"].lower(),
            "label": e["name"],
            "type": e.get("type", "concept"),
            "source_hash": e.get("source_hash", ""),
        }
        for e in all_entities
    ]

    edges = [
        {
            "source": r["source"].lower(),
            "target": r["target"].lower(),
            "relation": r.get("relation", "related_to"),
        }
        for r in all_relations
        if r["source"].lower() in seen_entities and r["target"].lower() in seen_entities
    ]

    return {
        "nodes": nodes,
        "edges": edges,
        "total_nodes": len(nodes),
        "total_edges": len(edges),
    }
