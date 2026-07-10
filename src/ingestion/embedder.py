"""
AyurKosha — Embedding Module
Embeds text using Cohere's multilingual model with *asymmetric* input types.

Asymmetry is a free accuracy boost: documents are embedded with
``input_type="search_document"`` and queries with ``input_type="search_query"``,
so the model accounts for the fact that queries are short/incomplete while
documents are long/declarative. Both sides land in the same 1024-dim space.

- Model: embed-multilingual-v3.0 (Sanskrit/Hindi/English) — from settings.
- Batching: documents are embedded in groups of 96 (Cohere's per-call cap).
- Resilience: transient errors / rate limits are retried with exponential
  backoff.

Build this in: Phase 2, Step 5
"""

from __future__ import annotations

import logging
import time
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

# Cohere accepts at most 96 texts per embed call.
MAX_BATCH = 96
# Retry policy for transient failures / rate limits.
MAX_RETRIES = 5
BASE_BACKOFF = 2.0  # seconds; doubles each retry

_client = None


def _get_client():
    """Lazily construct and cache the Cohere client."""
    global _client
    if _client is not None:
        return _client
    import cohere

    if not settings.cohere_api_key:
        raise RuntimeError(
            "COHERE_API_KEY is not set. Add it to .env before embedding."
        )
    _client = cohere.Client(api_key=settings.cohere_api_key)
    return _client


def _batched(items: list[Any], size: int):
    """Yield successive `size`-length slices of items."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _embed_with_retry(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed one batch (<= MAX_BATCH texts) with exponential backoff."""
    client = _get_client()
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.embed(
                texts=texts,
                model=settings.embedding_model,
                input_type=input_type,
                embedding_types=["float"],
            )
            # cohere v5: resp.embeddings.float ; older shape: resp.embeddings
            embeddings = getattr(resp.embeddings, "float", None)
            if embeddings is None:
                embeddings = resp.embeddings
            return [list(vec) for vec in embeddings]
        except Exception as exc:  # noqa: BLE001 — Cohere raises varied error types
            last_exc = exc
            wait = BASE_BACKOFF * (2 ** attempt)
            logger.warning(
                "Cohere embed failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError(
        f"Cohere embedding failed after {MAX_RETRIES} attempts: {last_exc}"
    )


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document texts (input_type='search_document').

    Batches internally in groups of 96 and returns one 1024-dim vector per
    input text, in the same order.
    """
    if not texts:
        return []
    vectors: list[list[float]] = []
    total_batches = (len(texts) + MAX_BATCH - 1) // MAX_BATCH
    for bi, batch in enumerate(_batched(texts, MAX_BATCH), start=1):
        logger.info("Embedding documents: batch %d/%d (%d texts).",
                    bi, total_batches, len(batch))
        vectors.extend(_embed_with_retry(batch, "search_document"))
    if vectors and len(vectors[0]) != settings.embedding_dimensions:
        logger.warning("Embedding dim %d != configured %d.",
                       len(vectors[0]), settings.embedding_dimensions)
    return vectors


def embed_query(query: str) -> list[float]:
    """Embed a single query (input_type='search_query'). Returns one vector."""
    if not query or not query.strip():
        raise ValueError("Cannot embed an empty query.")
    return _embed_with_retry([query], "search_query")[0]


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach an ``embedding`` field to each chunk dict.

    Args:
        chunks: Child chunk dicts with a ``text`` field.

    Returns:
        The same chunk dicts, each with a new ``embedding`` key (in place).
    """
    texts = [c.get("text", "") for c in chunks]
    vectors = embed_documents(texts)
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    return chunks
