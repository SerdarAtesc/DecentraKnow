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

    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
