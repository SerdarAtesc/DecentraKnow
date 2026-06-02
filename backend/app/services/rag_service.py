from app.services.embedding_service import generate_embedding
from app.services.vector_service import vector_service
from app.services.llm_service import get_provider, SYSTEM_PROMPT


async def rag_query(
    query: str,
    top_k: int = 3,
    category: str | None = None,
    provider: str | None = None,
) -> dict:
    query_embedding = await generate_embedding(query)

    filters = {}
    if category:
        filters["category"] = category

    results = vector_service.search(
        query_vector=query_embedding,
        top_k=top_k,
        filters=filters if filters else None,
    )

    context_parts = []
    sources = []
    for i, result in enumerate(results):
        payload = result["payload"]
        content = payload.get("content", "")
        title = payload.get("title", "Untitled")
        context_parts.append(f"[Source {i+1}: {title}]\n{content}\n")
        sources.append({
            "title": title,
            "content_hash": payload.get("content_hash", ""),
            "relevance_score": result["score"],
            "ipfs_cid": payload.get("ipfs_cid", ""),
        })

    context = "\n---\n".join(context_parts)
    user_message = f"Context:\n{context}\n\n---\nQuestion: {query}"

    llm = get_provider(provider)
    answer = await llm.generate(SYSTEM_PROMPT, user_message)

    return {
        "answer": answer,
        "sources": sources,
        "query": query,
        "provider": llm.name,
    }
