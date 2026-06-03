from fastapi import APIRouter, HTTPException, Header
from datetime import datetime, timezone
import asyncio
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
    PaidSearchRequest,
    PaidSearchResponse,
    PaidSearchResult,
    PaymentReceipt,
    EarningEntry,
    UploadPrepareResponse,
    UploadFinalizeRequest,
    UploadFinalizeResponse,
    X402DistributeRequest,
)
from app.services.embedding_service import (
    generate_embedding,
    compute_content_hash,
    compute_embedding_hash,
    cosine_similarity,
)
from app.services.simhash_service import simhash_hex
from app.services.vector_service import vector_service
from app.services.ipfs_service import ipfs_service
from app.services.blockchain_service import blockchain_service
from app.services.rag_service import rag_query
from app.services.llm_service import get_provider, SYSTEM_PROMPT
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
    sim_hash = simhash_hex(embedding)

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

    # Register on-chain first so we can persist the assigned record id alongside
    # the vector — the id is how on-chain search results map back to content.
    registration = await blockchain_service.register_knowledge(
        owner_public_key=request.owner,
        content_hash=content_hash,
        embedding_hash=embedding_hash,
        sim_hash=sim_hash,
        manifest_cid=ipfs_cid,
        source_url=source_url,
    )
    blockchain_tx = registration["tx_hash"] if registration else None
    record_id = registration["record_id"] if registration else None

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
            "sim_hash": sim_hash,
            "onchain_id": record_id,
            "timestamp": now,
        },
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
        sim_hash=sim_hash,
        ipfs_cid=ipfs_cid,
        blockchain_tx=blockchain_tx,
        record_id=record_id,
        title=title,
        duplicate=False,
        message="Knowledge asset registered successfully",
    )


# Wallet-signed upload (prepare -> wallet signs register -> finalize).
# Holds the heavy embedding between the two calls so we don't re-embed on finalize.
_pending_uploads: dict[str, dict] = {}


@router.post("/upload/prepare", response_model=UploadPrepareResponse)
async def upload_prepare(request: UploadRequest):
    """Off-chain work for an upload: embed, SimHash, IPFS. Returns the hashes the
    connected wallet needs to sign `register_knowledge` itself (so the owner is the
    user, not the backend). No chain write, no Qdrant write yet."""
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
    sim_hash = simhash_hex(embedding)

    semantic_dup = vector_service.check_semantic_duplicate(
        embedding, settings.similarity_threshold
    )
    if semantic_dup:
        return UploadPrepareResponse(
            duplicate=True,
            message=f"Semantic duplicate detected (similarity: {semantic_dup['score']:.4f})",
            content_hash=content_hash,
            sim_hash=sim_hash,
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

    # Stash everything finalize() needs (incl. the embedding) keyed by content_hash.
    _pending_uploads[content_hash] = {
        "embedding": embedding,
        "title": title,
        "content": content,
        "owner": request.owner,
        "category": request.category or "general",
        "language": request.language or "en",
        "source_url": source_url,
        "ipfs_cid": ipfs_cid,
        "embedding_hash": embedding_hash,
        "sim_hash": sim_hash,
        "timestamp": now,
    }

    return UploadPrepareResponse(
        duplicate=False,
        message="Ready to register on-chain. Sign with your wallet.",
        content_hash=content_hash,
        embedding_hash=embedding_hash,
        sim_hash=sim_hash,
        ipfs_cid=ipfs_cid,
        title=title,
        source_url=source_url,
    )


@router.post("/upload/finalize", response_model=UploadFinalizeResponse)
async def upload_finalize(request: UploadFinalizeRequest):
    """After the wallet has registered the record on-chain, persist the vector with
    the assigned on-chain id so search results map back to this content."""
    pending = _pending_uploads.pop(request.content_hash, None)
    if pending is None:
        raise HTTPException(
            status_code=404,
            detail="No pending upload for this content_hash (prepare expired or already finalized).",
        )

    vector_service.upsert(
        content_hash=request.content_hash,
        embedding=pending["embedding"],
        metadata={
            "title": pending["title"],
            "content": pending["content"][:2000],
            "owner": pending["owner"],
            "category": pending["category"],
            "language": pending["language"],
            "source_url": pending["source_url"],
            "ipfs_cid": pending["ipfs_cid"],
            "embedding_hash": pending["embedding_hash"],
            "sim_hash": pending["sim_hash"],
            "onchain_id": request.record_id,
            "timestamp": pending["timestamp"],
        },
    )

    try:
        await extract_entities_and_relations(
            content=pending["content"],
            content_hash=request.content_hash,
            title=pending["title"],
        )
    except Exception as e:
        print(f"[UploadFinalize] Graph extraction failed (non-blocking): {e}")

    return UploadFinalizeResponse(
        success=True,
        record_id=request.record_id,
        message="Knowledge registered on-chain and indexed.",
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


def owner_share(amount: int, owner_count: int) -> int:
    """Per-owner share of a paid search amount (stroops) after the platform cut. Integer
    division — the remainder stays with the platform. Shared by the XLM rail (pay_search) and
    the USDC agent rail (x402 distribute) so both split fees with the same on-chain bps."""
    if owner_count <= 0:
        return 0
    platform_bps = blockchain_service.get_platform_bps()
    owner_pool = amount - (amount * platform_bps // 10_000)
    return owner_pool // owner_count


async def run_search(query: str, top_k: int) -> dict:
    """Shared search core (no payment, no synthesis): embed -> on-chain Hamming rank
    -> off-chain cosine re-rank. Returns results + result_ids + id_map + relevance.

    Used by both the XLM human rail (/search/paid) and the USDC x402 agent rail
    (/x402/run), so ranking/relevance behavior is identical across both.
    """
    embedding = await generate_embedding(query)
    query_sim_hash = simhash_hex(embedding)

    hits = blockchain_service.onchain_search(query_sim_hash, top_k)
    if not hits:
        return {"results": [], "result_ids": [], "id_map": {}, "relevant": False,
                "message": "No matching records on-chain."}

    best_distance = min(h["distance"] for h in hits)
    if best_distance > settings.simhash_distance_threshold:
        return {"results": [], "result_ids": [], "id_map": {}, "relevant": False,
                "message": (f"No confident match (closest Hamming distance {best_distance} > "
                            f"threshold {settings.simhash_distance_threshold}).")}

    # Map on-chain ids -> stored vector + payload.
    id_map = {
        v["payload"].get("onchain_id"): v
        for v in vector_service.get_all_vectors(limit=500)
        if v["payload"].get("onchain_id") is not None
    }

    # Off-chain re-rank: 256-bit Hamming order is coarse, so a barely-relevant neighbor
    # can sit only a few bits behind a real match. Re-score by TRUE cosine and keep only
    # those clearing both an absolute floor and a relative margin from the best match.
    scored = []
    for hit in hits:
        entry = id_map.get(hit["id"])
        if entry is None:
            continue
        cos = cosine_similarity(embedding, entry["vector"])
        scored.append((hit, entry["payload"], cos))

    cutoff = settings.rerank_cosine_threshold
    if scored:
        best_cos = max(c for _, _, c in scored)
        cutoff = max(cutoff, best_cos - settings.rerank_relative_margin)

    results: list[PaidSearchResult] = []
    result_ids: list[int] = []
    for hit, payload, cos in scored:
        if cos < cutoff:
            continue
        result_ids.append(hit["id"])
        results.append(
            PaidSearchResult(
                record_id=hit["id"],
                distance=hit["distance"],
                content_hash=payload.get("content_hash", ""),
                title=payload.get("title", "Untitled"),
                content_preview=payload.get("content", "")[:300],
                owner=payload.get("owner", ""),
                ipfs_cid=payload.get("ipfs_cid", ""),
            )
        )

    if not result_ids:
        return {"results": [], "result_ids": [], "id_map": id_map, "relevant": False,
                "message": "No relevant match after re-ranking the on-chain candidates."}

    return {"results": results, "result_ids": result_ids, "id_map": id_map,
            "relevant": True, "message": "ok"}


async def synthesize_answer(query, results, id_map, provider=None):
    """RAG: combine the ranked sources into one grounded answer. Best-effort."""
    context_parts = []
    for i, r in enumerate(results):
        entry = id_map.get(r.record_id) or {}
        content = (entry.get("payload", {}).get("content") if entry else None) or r.content_preview
        if content:
            context_parts.append(f"[Source {i + 1}: {r.title}]\n{content}\n")
    if not context_parts:
        return None
    try:
        context = "\n---\n".join(context_parts)
        user_message = f"Context:\n{context}\n\n---\nQuestion: {query}"
        llm = get_provider(provider)
        return await llm.generate(SYSTEM_PROMPT, user_message)
    except Exception as e:
        print(f"[Search] RAG synthesis failed (non-blocking): {e}")
        return None


@router.post("/search/paid", response_model=PaidSearchResponse)
async def paid_onchain_search(request: PaidSearchRequest):
    """Human rail: paid (XLM credit) blockchain-native search with RAG synthesis."""
    core = await run_search(request.query, request.top_k)
    if not core["relevant"]:
        return PaidSearchResponse(
            results=[], query=request.query,
            payment=PaymentReceipt(charged=False, price=0, platform_cut=0, owner_earnings=[]),
            message=core["message"] + " Nothing charged.",
        )

    results, result_ids, id_map = core["results"], core["result_ids"], core["id_map"]

    # Payment gate: deliver NOTHING unless the search is paid (XLM credits).
    price = blockchain_service.get_search_price()
    credits = blockchain_service.get_credits(request.payer)
    if credits < price:
        return PaidSearchResponse(
            results=[], query=request.query, answer=None,
            payment=PaymentReceipt(charged=False, price=0, platform_cut=0, owner_earnings=[]),
            message=(f"Insufficient credit: you have {credits} stroops, a search costs {price}. "
                     f"Add funds in Wallet & Earnings."),
        )

    tx_hash = await blockchain_service.pay_search(request.payer, result_ids)
    if not tx_hash:
        return PaidSearchResponse(
            results=[], query=request.query, answer=None,
            payment=PaymentReceipt(charged=False, price=0, platform_cut=0, owner_earnings=[]),
            message="Payment could not be settled on-chain. Nothing delivered.",
        )

    share = owner_share(price, len(result_ids))
    earnings: dict[str, int] = {}
    for r in results:
        if r.owner:
            earnings[r.owner] = earnings.get(r.owner, 0) + share
    receipt = PaymentReceipt(
        charged=True, tx_hash=tx_hash, price=price,
        platform_cut=price - share * len(result_ids),
        owner_earnings=[EarningEntry(owner=o, amount=a) for o, a in earnings.items()],
    )

    answer = await synthesize_answer(request.query, results, id_map, request.provider)
    return PaidSearchResponse(
        results=results, query=request.query, answer=answer, payment=receipt,
        message="Search settled on-chain; owners credited.",
    )


@router.post("/x402/run")
async def x402_run(request: PaidSearchRequest, x_internal_secret: str = Header(default="")):
    """Agent rail (x402): payment-free search core. Payment is enforced UPSTREAM by the
    x402 Node gateway (USDC, facilitator-settled); this internal endpoint is guarded by
    a shared secret so it is not a public bypass of the paid search."""
    if not settings.x402_internal_secret or x_internal_secret != settings.x402_internal_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Secret")

    core = await run_search(request.query, request.top_k)
    if not core["relevant"]:
        return {"results": [], "query": request.query, "answer": None,
                "result_ids": [], "owners": [], "message": core["message"]}

    answer = await synthesize_answer(request.query, core["results"], core["id_map"], request.provider)
    owners: list[str] = []
    for r in core["results"]:
        if r.owner and r.owner not in owners:
            owners.append(r.owner)
    return {
        "results": [r.model_dump() for r in core["results"]],
        "query": request.query,
        "answer": answer,
        "result_ids": core["result_ids"],
        "owners": owners,
        "message": "Paid via x402; results delivered.",
    }


# Serialize admin USDC payouts so concurrent (parallel-agent) distributes never race on the
# admin account's sequence number. Background payouts drain through this one lock.
_payout_lock = asyncio.Lock()


async def _run_payouts(owners: list[str], share: int) -> None:
    """Send `share` USDC to each owner, one at a time (lock-serialized, off the event loop)."""
    loop = asyncio.get_running_loop()
    async with _payout_lock:
        for owner in owners:
            try:
                await loop.run_in_executor(None, blockchain_service.send_usdc, owner, share)
            except Exception as e:  # a single failed payout shouldn't abort the rest
                print(f"[x402] background payout to {owner[:8]}… failed: {e}")


@router.post("/x402/distribute")
async def x402_distribute(request: X402DistributeRequest, x_internal_secret: str = Header(default="")):
    """Per-creator USDC payout on the agent rail. After an x402 search settles USDC to the
    platform, split the owner pool among the result owners and send each their share in USDC.
    Owners without a USDC trustline (or contract addresses, or the platform itself) are
    skipped and their share stays with the platform. Guarded by the shared secret.

    With `background=true` the trustline-aware split is computed and returned immediately while
    the actual on-chain USDC sends run async (lock-serialized) — so a parallel agent doesn't
    block on settlement latency. Sync mode (default) waits and returns each payout's tx hash."""
    if not settings.x402_internal_secret or x_internal_secret != settings.x402_internal_secret:
        raise HTTPException(status_code=401, detail="Invalid or missing X-Internal-Secret")

    platform = blockchain_service.admin_public_key
    owners = [o for o in dict.fromkeys(request.owners) if o and o != platform]  # dedupe, drop platform
    if not owners or request.amount <= 0:
        return {"distributed": [], "skipped": request.owners, "platform_kept": request.amount, "share": 0}

    share = owner_share(request.amount, len(owners))

    if request.background:
        # Compute the trustline-aware split now; fire the real USDC sends in the background.
        payable = [o for o in owners if share > 0 and blockchain_service.has_usdc_trustline(o)]
        skipped = [o for o in owners if o not in payable]
        if payable:
            asyncio.create_task(_run_payouts(payable, share))
        distributed = [{"owner": o, "amount": share, "tx": None} for o in payable]
        platform_kept = request.amount - share * len(payable)
        return {"distributed": distributed, "skipped": skipped, "platform_kept": platform_kept,
                "share": share, "pending": True}

    distributed, skipped = [], []
    async with _payout_lock:
        loop = asyncio.get_running_loop()
        for owner in owners:
            tx = await loop.run_in_executor(None, blockchain_service.send_usdc, owner, share) if share > 0 else None
            if tx:
                distributed.append({"owner": owner, "amount": share, "tx": tx})
            else:
                skipped.append(owner)

    platform_kept = request.amount - sum(d["amount"] for d in distributed)
    return {"distributed": distributed, "skipped": skipped, "platform_kept": platform_kept, "share": share}


@router.get("/account/{public_key}")
async def account_balances(public_key: str):
    """On-chain credit + earnings for a given account (read-only, free)."""
    return {
        "public_key": public_key,
        "credits": blockchain_service.get_credits(public_key),
        "earnings": blockchain_service.get_earnings(public_key),
        "search_price": blockchain_service.get_search_price(),
    }


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
