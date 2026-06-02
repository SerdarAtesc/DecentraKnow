import numpy as np
from app.core.config import get_settings

settings = get_settings()

_qdrant_available = False
try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import (
        Distance,
        VectorParams,
        PointStruct,
        Filter,
        FieldCondition,
        MatchValue,
        PayloadSchemaType,
    )
    _qdrant_available = True
except ImportError:
    pass


class VectorService:
    """
    Vector database service with Qdrant backend.
    Falls back to in-memory storage if Qdrant is unavailable.
    """

    def __init__(self):
        self._client = None
        self._connected = False
        self._memory_store: list[dict] = []
        self.collection = settings.qdrant_collection
        self._try_connect()

    def _try_connect(self):
        if not _qdrant_available:
            print("[VectorService] Qdrant client not installed, using in-memory fallback")
            return

        try:
            if settings.qdrant_url and settings.qdrant_api_key:
                self._client = QdrantClient(
                    url=settings.qdrant_url,
                    api_key=settings.qdrant_api_key,
                    timeout=10,
                )
                print(f"[VectorService] Connecting to Qdrant Cloud...")
            else:
                self._client = QdrantClient(
                    host=settings.qdrant_host,
                    port=settings.qdrant_port,
                    timeout=3,
                )

            collections = self._client.get_collections().collections
            exists = any(c.name == self.collection for c in collections)
            if not exists:
                self._client.create_collection(
                    collection_name=self.collection,
                    vectors_config=VectorParams(
                        size=settings.embedding_dimensions,
                        distance=Distance.COSINE,
                    ),
                )
            self._ensure_indexes()
            self._connected = True
            print(f"[VectorService] Connected to Qdrant successfully")
        except Exception as e:
            print(f"[VectorService] Qdrant unavailable ({e}), using in-memory fallback")
            self._client = None
            self._connected = False

    def _ensure_indexes(self):
        try:
            for field in ["content_hash", "owner", "category", "language"]:
                self._client.create_payload_index(
                    collection_name=self.collection,
                    field_name=field,
                    field_schema=PayloadSchemaType.KEYWORD,
                )
        except Exception:
            pass

    def upsert(self, content_hash: str, embedding: list[float], metadata: dict) -> str:
        from uuid import uuid4
        point_id = str(uuid4())

        if self._connected and self._client:
            self._client.upsert(
                collection_name=self.collection,
                points=[
                    PointStruct(
                        id=point_id,
                        vector=embedding,
                        payload={"content_hash": content_hash, **metadata},
                    )
                ],
            )
        else:
            self._memory_store.append({
                "id": point_id,
                "vector": embedding,
                "payload": {"content_hash": content_hash, **metadata},
            })

        return point_id

    def search(self, query_vector: list[float], top_k: int = 5, filters: dict | None = None) -> list[dict]:
        if self._connected and self._client:
            return self._qdrant_search(query_vector, top_k, filters)
        return self._memory_search(query_vector, top_k, filters)

    def _qdrant_search(self, query_vector: list[float], top_k: int, filters: dict | None) -> list[dict]:
        filter_conditions = []
        if filters:
            for key, value in filters.items():
                if value is not None:
                    filter_conditions.append(
                        FieldCondition(key=key, match=MatchValue(value=value))
                    )

        qdrant_filter = Filter(must=filter_conditions) if filter_conditions else None

        results = self._client.search(
            collection_name=self.collection,
            query_vector=query_vector,
            limit=top_k,
            query_filter=qdrant_filter,
            with_payload=True,
        )

        return [{"score": hit.score, "payload": hit.payload} for hit in results]

    def _memory_search(self, query_vector: list[float], top_k: int, filters: dict | None) -> list[dict]:
        if not self._memory_store:
            return []

        query = np.array(query_vector)
        scored = []

        for item in self._memory_store:
            payload = item["payload"]

            if filters:
                skip = False
                for key, value in filters.items():
                    if value is not None and payload.get(key) != value:
                        skip = True
                        break
                if skip:
                    continue

            vec = np.array(item["vector"])
            similarity = float(np.dot(query, vec) / (np.linalg.norm(query) * np.linalg.norm(vec) + 1e-10))
            scored.append({"score": similarity, "payload": payload})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def check_semantic_duplicate(self, embedding: list[float], threshold: float) -> dict | None:
        results = self.search(query_vector=embedding, top_k=1)
        if results and results[0]["score"] >= threshold:
            return results[0]
        return None

    def get_all_vectors(self, limit: int = 500) -> list[dict]:
        if self._connected and self._client:
            results = self._client.scroll(
                collection_name=self.collection,
                limit=limit,
                with_vectors=True,
                with_payload=True,
            )
            points = results[0]
            return [{"vector": point.vector, "payload": point.payload} for point in points]

        return [{"vector": item["vector"], "payload": item["payload"]} for item in self._memory_store[:limit]]


vector_service = VectorService()
