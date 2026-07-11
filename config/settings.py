"""
AyurKosha — Central Configuration
Loads all settings from .env and provides them to the application.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── API Keys ───────────────────────────────────────────
    anthropic_api_key: str = ""
    cohere_api_key: str = ""
    pinecone_api_key: str = ""
    pinecone_environment: str = "us-east-1"
    pinecone_index_name: str = "ayurkosha"

    # ── Redis ──────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Pipeline Parameters ────────────────────────────────
    top_k_final: int = 6
    bm25_retrieve_n: int = 50
    semantic_retrieve_n: int = 50
    rerank_first_pass_n: int = 15
    rrf_k: int = 60

    # ── Embedding ──────────────────────────────────────────
    embedding_model: str = "embed-multilingual-v3.0"
    embedding_dimensions: int = 1024
    # Client-side throttle to respect Cohere rate limits. Trial keys allow
    # 100k tokens/min; default leaves headroom (token estimates undercount
    # diacritic/Devanagari text). Raise this on a production key.
    cohere_tokens_per_min: int = 80000

    # ── Generation ─────────────────────────────────────────
    generation_model: str = "claude-sonnet-4-6"

    # ── Logging ────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
