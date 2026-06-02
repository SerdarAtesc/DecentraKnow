import hashlib
import numpy as np
from openai import AsyncOpenAI
from app.core.config import get_settings

settings = get_settings()
client = AsyncOpenAI(api_key=settings.openai_api_key)


async def generate_embedding(text: str) -> list[float]:
    text = text.replace("\n", " ").strip()
    if not text:
        raise ValueError("Empty text cannot be embedded")

    response = await client.embeddings.create(
        input=text,
        model=settings.openai_embedding_model,
    )
    return response.data[0].embedding


def compute_content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def compute_embedding_hash(embedding: list[float]) -> str:
    embedding_bytes = np.array(embedding, dtype=np.float32).tobytes()
    return hashlib.sha256(embedding_bytes).hexdigest()


def cosine_similarity(vec_a: list[float], vec_b: list[float]) -> float:
    a = np.array(vec_a)
    b = np.array(vec_b)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
