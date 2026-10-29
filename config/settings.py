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

    # ── Corpus text fixes (take effect on the next ingestion) ──
    # Legacy-font -> IAST character maps (src/ingestion/text_cleanup.py),
    # confirmed 2026-10-29 (docs/corpus_text_fixes.md).
    apply_font_char_map: bool = True
    # BM25 tokenizer + synonym lookup: fold Latin diacritics (ā->a) so IAST
    # words stay whole, and add romanization keys (src/utils/transliterate.py)
    # so "Ashwagandha" matches "Aśvagandhā". Applies to documents and queries.
    bm25_fold_diacritics: bool = True
    # Split run-together OCR words in BM25 text (Sushruta vol 1-2). Display,
    # citations, and embeddings keep the original text. Approved 2026-10-29
    # (samples in docs/corpus_text_fixes.md).
    split_glued_ocr_words: bool = True
    # Prepend "[Work] > [Section] > [Herb/Formulation]" to the text used for
    # embedding and reranking (src/ingestion/context_headers.py). Raw text is
    # kept for display/citations. Needs a full re-embed to take effect.
    contextual_chunk_headers: bool = True
    # Skip Charaka Samhita at ingestion: the scan's text layer is unusable
    # (English translation OCR'd as Devanagari). Re-enable after re-OCR.
    exclude_charaka: bool = True
    # Ashtanga Hridaya volumes no English query can match (audit in
    # docs/corpus_text_fixes.md): Srikantha Murthy vol 1 is an English book
    # OCR'd with a Hindi engine; the Sanskrit commentaries are Devanagari-only.
    exclude_ah_srikantha_murthy: bool = True
    exclude_ah_sanskrit_commentaries: bool = True

    # ── Reranking (eval path) ──────────────────────────────
    # The eval reranks with retry + client-side pacing so every question is
    # actually reranked. Trial keys allow 10 rerank calls/min; raise this on a
    # production key (0 disables pacing).
    cohere_rerank_calls_per_min: int = 10
    rerank_max_retries: int = 5
    rerank_backoff_base: float = 6.0  # seconds; doubles each retry

    # ── Generation ─────────────────────────────────────────
    generation_model: str = "claude-sonnet-4-6"
    # Output ceiling for answer generation. Cited, table-rich answers run long;
    # 2000 truncated them mid-sentence, so give comfortable headroom.
    generation_max_tokens: int = 4096
    # Cheap/fast model for classification-style calls (query expansion,
    # doc_type filter inference) — no need for the full generation model.
    query_expansion_model: str = "claude-haiku-4-5-20251001"

    # ── Logging ────────────────────────────────────────────
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
