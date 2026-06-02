from fastapi import APIRouter, HTTPException
from datetime import datetime, timezone
import numpy as np
from sklearn.decomposition import PCA

from app.models.schemas import (
    UploadRequest,
    UploadResponse,
    SearchRequest,
    SearchResponse,
    SearchResult,
    RAGRequest,
    RAGResponse,
    RAGSource,
    EmbedRequest,
    EmbedResponse,
    FetchURLRequest,
    FetchURLResponse,
    RenderResponse,
    RenderPoint,
    KnowledgeManifest,
)
from app.services.embedding_service import (
    generate_embedding,
    compute_content_hash,
    compute_embedding_hash,
)
from app.services.vector_service import vector_service
from app.services.ipfs_service import ipfs_service
from app.services.blockchain_service import blockchain_service
from app.services.rag_service import rag_query
from app.services.scraper_service import fetch_and_extract
from app.services.graph_service import extract_entities_and_relations, get_graph
from app.core.config import get_settings

settings = get_settings()
router = APIRouter()


@router.post("/upload", response_model=UploadResponse)
async def upload_knowledge(request: UploadRequest):
    if not request.content and not request.url:
        raise HTTPException(status_code=400, detail="Either content or url is required")

    content = request.content or ""
    source_url = request.url or ""
    title = request.title or ""

    if request.url and not request.content:
        try:
            extracted = await fetch_and_extract(request.url)
            content = extracted["content"]
            if not title:
                title = extracted["title"]
            source_url = request.url
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")

    if not content.strip():
        raise HTTPException(status_code=400, detail="No content to process")

    if not title:
        title = content[:80].replace("\n", " ").strip()

    content_hash = compute_content_hash(content)

    embedding = await generate_embedding(content)
    embedding_hash = compute_embedding_hash(embedding)

    semantic_dup = vector_service.check_semantic_duplicate(
        embedding, settings.similarity_threshold
    )
    if semantic_dup:
        return UploadResponse(
            success=False,
            content_hash=content_hash,
            embedding_hash=embedding_hash,
            ipfs_cid="",
            title=title,
            duplicate=True,
            message=f"Semantic duplicate detected (similarity: {semantic_dup['score']:.4f})",
        )

    now = datetime.now(timezone.utc).isoformat()

    manifest = KnowledgeManifest(
        title=title,
        content=content,
        content_hash=content_hash,
        embedding_hash=embedding_hash,
        source_url=source_url,
        owner=request.owner,
        category=request.category or "general",
        language=request.language or "en",
        created_at=now,
    )

    ipfs_cid = await ipfs_service.upload_json(manifest.model_dump())

    vector_service.upsert(
        content_hash=content_hash,
        embedding=embedding,
        metadata={
            "title": title,
            "content": content[:2000],
            "owner": request.owner,
            "category": request.category or "general",
            "language": request.language or "en",
            "source_url": source_url,
            "ipfs_cid": ipfs_cid,
            "embedding_hash": embedding_hash,
            "timestamp": now,
        },
    )

    blockchain_tx = await blockchain_service.register_knowledge(
        owner_public_key=request.owner,
        content_hash=content_hash,
        embedding_hash=embedding_hash,
        manifest_cid=ipfs_cid,
        source_url=source_url,
    )

    try:
        await extract_entities_and_relations(
            content=content,
            content_hash=content_hash,
            title=title,
        )
    except Exception as e:
        print(f"[Upload] Graph extraction failed (non-blocking): {e}")

    return UploadResponse(
        success=True,
        content_hash=content_hash,
        embedding_hash=embedding_hash,
        ipfs_cid=ipfs_cid,
        blockchain_tx=blockchain_tx,
        title=title,
        duplicate=False,
        message="Knowledge asset registered successfully",
    )


@router.post("/search", response_model=SearchResponse)
async def search_knowledge(request: SearchRequest):
    query_embedding = await generate_embedding(request.query)

    filters = {}
    if request.category:
        filters["category"] = request.category
    if request.language:
        filters["language"] = request.language
    if request.owner:
        filters["owner"] = request.owner

    results = vector_service.search(
        query_vector=query_embedding,
        top_k=request.top_k,
        filters=filters if filters else None,
    )

    search_results = []
    for r in results:
        payload = r["payload"]
        search_results.append(
            SearchResult(
                content_hash=payload.get("content_hash", ""),
                title=payload.get("title", "Untitled"),
                content_preview=payload.get("content", "")[:300],
                score=r["score"],
                category=payload.get("category", "general"),
                language=payload.get("language", "en"),
                owner=payload.get("owner", ""),
                ipfs_cid=payload.get("ipfs_cid", ""),
                timestamp=payload.get("timestamp", ""),
            )
        )

    return SearchResponse(
        results=search_results,
        query=request.query,
        total=len(search_results),
    )


@router.post("/rag", response_model=RAGResponse)
async def rag_endpoint(request: RAGRequest):
    try:
        result = await rag_query(
            query=request.query,
            top_k=request.top_k,
            category=request.category,
            provider=request.provider,
        )
        return RAGResponse(
            answer=result["answer"],
            sources=[RAGSource(**s) for s in result["sources"]],
            query=result["query"],
            provider=result.get("provider"),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")


@router.get("/providers")
async def list_providers():
    from app.services.llm_service import get_available_providers
    return {"providers": get_available_providers()}


@router.get("/graph")
async def get_knowledge_graph(entity_type: str | None = None, limit: int = 200):
    graph_data = get_graph(limit=limit, entity_type=entity_type)
    return graph_data


@router.post("/graph/rebuild")
async def rebuild_knowledge_graph():
    """Re-extract graph entities from all existing records in the vector DB."""
    from app.services.graph_service import _clear_graph_store

    all_records = vector_service.get_all_vectors(limit=500)
    if not all_records:
        raise HTTPException(status_code=404, detail="No records found in vector DB")

    _clear_graph_store()
    processed = 0
    errors = 0

    for record in all_records:
        payload = record.get("payload", {})
        content = payload.get("content", "")
        title = payload.get("title", "Untitled")
        content_hash = payload.get("content_hash", "")

        if not content or not content_hash:
            continue

        try:
            await extract_entities_and_relations(
                content=content,
                content_hash=content_hash,
                title=title,
            )
            processed += 1
        except Exception as e:
            print(f"[GraphRebuild] Error for '{title}': {e}")
            errors += 1

    graph_data = get_graph()
    return {
        "message": f"Graph rebuilt from {processed} records ({errors} errors)",
        "total_nodes": graph_data["total_nodes"],
        "total_edges": graph_data["total_edges"],
    }


@router.post("/embed", response_model=EmbedResponse)
async def embed_text(request: EmbedRequest):
    if not request.text.strip():
        raise HTTPException(status_code=400, detail="Text cannot be empty")

    embedding = await generate_embedding(request.text)
    return EmbedResponse(
        embedding=embedding,
        dimensions=len(embedding),
        model=settings.openai_embedding_model,
    )


@router.post("/fetch-url", response_model=FetchURLResponse)
async def fetch_url(request: FetchURLRequest):
    try:
        result = await fetch_and_extract(request.url)
        return FetchURLResponse(**result)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to fetch URL: {e}")


@router.get("/render", response_model=RenderResponse)
async def render_embeddings():
    all_vectors = vector_service.get_all_vectors(limit=500)

    if len(all_vectors) < 2:
        return RenderResponse(points=[], method="pca", total_points=0)

    vectors = np.array([v["vector"] for v in all_vectors])

    n_components = min(2, vectors.shape[0], vectors.shape[1])
    pca = PCA(n_components=n_components)
    coords = pca.fit_transform(vectors)

    points = []
    for i, v in enumerate(all_vectors):
        payload = v["payload"]
        points.append(
            RenderPoint(
                x=float(coords[i][0]),
                y=float(coords[i][1]) if n_components > 1 else 0.0,
                content_hash=payload.get("content_hash", ""),
                title=payload.get("title", "Untitled"),
                category=payload.get("category", "general"),
            )
        )

    return RenderResponse(
        points=points,
        method="pca",
        total_points=len(points),
    )
