from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UploadRequest(BaseModel):
    content: Optional[str] = None
    url: Optional[str] = None
    owner: str = Field(..., description="Stellar public key of the owner")
    category: Optional[str] = "general"
    language: Optional[str] = "en"
    title: Optional[str] = None


class UploadResponse(BaseModel):
    success: bool
    content_hash: str
    embedding_hash: str
    ipfs_cid: str
    blockchain_tx: Optional[str] = None
    title: str
    duplicate: bool = False
    message: str


class SearchRequest(BaseModel):
    query: str
    top_k: int = Field(default=5, ge=1, le=50)
    category: Optional[str] = None
    language: Optional[str] = None
    owner: Optional[str] = None


class SearchResult(BaseModel):
    content_hash: str
    title: str
    content_preview: str
    score: float
    category: str
    language: str
    owner: str
    ipfs_cid: str
    timestamp: str


class SearchResponse(BaseModel):
    results: list[SearchResult]
    query: str
    total: int


class RAGRequest(BaseModel):
    query: str
    top_k: int = Field(default=3, ge=1, le=10)
    category: Optional[str] = None
    provider: Optional[str] = None


class RAGSource(BaseModel):
    title: str
    content_hash: str
    relevance_score: float
    ipfs_cid: str


class RAGResponse(BaseModel):
    answer: str
    sources: list[RAGSource]
    query: str
    provider: Optional[str] = None


class EmbedRequest(BaseModel):
    text: str


class EmbedResponse(BaseModel):
    embedding: list[float]
    dimensions: int
    model: str


class FetchURLRequest(BaseModel):
    url: str


class FetchURLResponse(BaseModel):
    url: str
    title: str
    content: str
    word_count: int


class KnowledgeManifest(BaseModel):
    title: str
    content: str
    content_hash: str
    embedding_hash: str
    source_url: Optional[str] = None
    owner: str
    category: str
    language: str
    created_at: str


class RenderPoint(BaseModel):
    x: float
    y: float
    content_hash: str
    title: str
    category: str


class RenderResponse(BaseModel):
    points: list[RenderPoint]
    method: str
    total_points: int
