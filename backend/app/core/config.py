from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "DecentraKnow"
    app_version: str = "0.1.0"
    debug: bool = False

    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_chat_model: str = "gpt-4o-mini"
    embedding_dimensions: int = 1536

    anthropic_api_key: str = ""
    google_api_key: str = ""
    default_llm_provider: str = "openai"

    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection: str = "knowledge_vectors"

    ipfs_api_url: str = "/dns/localhost/tcp/5001/http"
    pinata_jwt: str = ""

    stellar_network: str = "testnet"
    stellar_rpc_url: str = "https://soroban-testnet.stellar.org"
    stellar_network_passphrase: str = "Test SDF Network ; September 2015"
    contract_id: str = ""
    stellar_secret_key: str = ""

    similarity_threshold: float = 0.92
    search_top_k: int = 5
    rag_context_limit: int = 3

    # SimHash / LSH — must match the on-chain contract's expectations and be
    # identical across every node. Changing the seed invalidates all stored hashes.
    simhash_seed: int = 1337
    # On-chain search settlement (paid search). Public key whose signature settles
    # pay_search is the contract admin; the backend signs with stellar_secret_key.
    onchain_search_top_k: int = 5
    # Max acceptable Hamming distance (out of 256) for a result to count as a real
    # match. If the closest result exceeds this, we treat it as "no confident match":
    # no RAG synthesis, no charge. Tune per corpus; ~random is 128, good matches < 100.
    simhash_distance_threshold: int = 110
    # Off-chain re-rank: after the coarse on-chain Hamming ranking, candidates are
    # re-scored by true cosine similarity and only those above this threshold count
    # as relevant (so only relevant owners get paid). OpenAI embeddings: related
    # pairs are typically > 0.3, unrelated < 0.2.
    rerank_cosine_threshold: float = 0.28
    # On top of the absolute floor, drop results that trail the BEST match by more
    # than this. Adaptive: when one result clearly wins (e.g. "proof of work" ->
    # Bitcoin), topic-adjacent neighbors are pruned; when several score similarly,
    # they're all kept.
    rerank_relative_margin: float = 0.18

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
