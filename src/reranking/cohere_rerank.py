"""
AyurKosha — Cohere Cross-Encoder Reranking
Second-stage reranking of the fused candidate set. Unlike the bi-encoder
retrieval (which embeds query and passage separately), the cross-encoder reads
the query and each passage *together*, giving a much sharper relevance signal.

Model: rerank-multilingual-v3.0 (handles Sanskrit/Hindi/English passages).

Fails safe: if the Cohere call errors (network / rate limit / no key), the
original top_n candidates are returned unchanged so the pipeline degrades
gracefully instead of breaking.

Build this in: Phase 3, Step 4
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

RERANK_MODEL = "rerank-multilingual-v3.0"

_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client
    import cohere

    if not settings.cohere_api_key:
        raise RuntimeError("COHERE_API_KEY is not set.")
    _client = cohere.Client(api_key=settings.cohere_api_key)
    return _client


def rerank(
    query: str,
    results: list[dict[str, Any]],
    top_n: int | None = None,
    model: str = RERANK_MODEL,
) -> list[dict[str, Any]]:
    """Rerank candidate results against the query with a Cohere cross-encoder.

    Args:
        query: The (original) user query.
        results: Candidate result dicts, each with a ``text`` field.
        top_n: Keep this many after reranking (default settings.rerank_first_pass_n).
        model: Cohere rerank model id.

    Returns:
        Reranked result dicts (<= top_n), each with an added ``rerank_score``
        and recomputed ``rank``. On any error, returns the input's first top_n
        unchanged.
    """
    top_n = top_n or settings.rerank_first_pass_n
    if not results:
        return []

    documents = [r.get("text", "") for r in results]
    keep = min(top_n, len(results))
    try:
        client = _get_client()
        resp = client.rerank(
            query=query,
            documents=documents,
            top_n=keep,
            model=model,
        )
        reranked: list[dict[str, Any]] = []
        for rank, item in enumerate(resp.results):
            r = dict(results[item.index])
            r["rerank_score"] = float(item.relevance_score)
            r["rank"] = rank
            reranked.append(r)
        logger.info("Cohere rerank: %d candidates -> top %d.",
                    len(results), len(reranked))
        return reranked
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any failure
        logger.warning("Cohere rerank failed (%s); returning unranked top %d.",
                       exc, keep)
        return results[:keep]
