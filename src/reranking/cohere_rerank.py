"""
AyurKosha — Cohere Cross-Encoder Reranking
Second-stage reranking of the fused candidate set. Unlike the bi-encoder
retrieval (which embeds query and passage separately), the cross-encoder reads
the query and each passage *together*, giving a much sharper relevance signal.

Model: rerank-multilingual-v3.0 (handles Sanskrit/Hindi/English passages).

Fails safe: if the Cohere call errors (network / rate limit / no key), the
original top_n candidates are returned unchanged so the pipeline degrades
gracefully instead of breaking.

The eval uses ``rerank_with_retry`` instead: it paces calls under
settings.cohere_rerank_calls_per_min and retries 429s with exponential
backoff, and reports whether reranking was ultimately skipped — an unranked
fallback silently contaminates retrieval metrics. A monthly-quota 429 raises
CohereQuotaExhausted immediately (no retries) so the eval aborts clearly.

Build this in: Phase 3, Step 4
"""

from __future__ import annotations

import logging
import time
from typing import Any

from config.settings import settings
from src.ingestion.context_headers import contextual_text
from src.ingestion.embedder import _is_rate_limit, raise_if_quota_exhausted

logger = logging.getLogger(__name__)

RERANK_MODEL = "rerank-multilingual-v3.0"

_client = None
# Monotonic time of the last paced rerank call (rerank_with_retry only).
_last_call_at: float | None = None


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
    query_id: str | None = None,
) -> list[dict[str, Any]]:
    """Rerank candidate results against the query with a Cohere cross-encoder.

    Args:
        query: The (original) user query.
        results: Candidate result dicts, each with a ``text`` field.
        top_n: Keep this many after reranking (default settings.rerank_first_pass_n).
        model: Cohere rerank model id.
        query_id: Request id included in the skip warning, so a degraded
            answer can be traced back to its request.

    Returns:
        Reranked result dicts (<= top_n), each with an added ``rerank_score``
        and recomputed ``rank``. On any error, returns the input's first top_n
        unchanged.
    """
    top_n = top_n or settings.rerank_first_pass_n
    if not results:
        return []

    keep = min(top_n, len(results))
    try:
        return _call_rerank(query, results, keep, model)
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any failure
        logger.warning("Rerank SKIPPED for query_id=%s: Cohere rerank failed (%s); "
                       "returning unranked top %d.", query_id or "-", exc, keep)
        return results[:keep]


def rerank_with_retry(
    query: str,
    results: list[dict[str, Any]],
    top_n: int | None = None,
    model: str = RERANK_MODEL,
) -> tuple[list[dict[str, Any]], bool]:
    """Rerank with client-side pacing and 429 retry/backoff (eval path).

    Returns:
        ``(results, skipped)``. ``skipped`` is True when reranking failed after
        all retries (or on a non-rate-limit error) and the unranked top_n
        fallback was returned instead.

    Raises:
        CohereQuotaExhausted: the key's monthly quota is used up.
    """
    top_n = top_n or settings.rerank_first_pass_n
    if not results:
        return [], False

    keep = min(top_n, len(results))
    retries = settings.rerank_max_retries
    for attempt in range(retries + 1):
        _pace()
        try:
            return _call_rerank(query, results, keep, model), False
        except Exception as exc:  # noqa: BLE001 — Cohere raises varied error types
            raise_if_quota_exhausted(exc, "rerank")
            if not _is_rate_limit(exc) or attempt == retries:
                logger.warning("Cohere rerank failed after %d attempt(s) (%s); "
                               "returning unranked top %d.", attempt + 1, exc, keep)
                return results[:keep], True
            wait = settings.rerank_backoff_base * (2 ** attempt)
            logger.warning("Cohere rerank rate-limited (attempt %d/%d); retrying in %.1fs.",
                           attempt + 1, retries + 1, wait)
            time.sleep(wait)
    return results[:keep], True  # pragma: no cover — loop always returns


def _pace() -> None:
    """Sleep so paced calls stay under settings.cohere_rerank_calls_per_min."""
    global _last_call_at
    rate = settings.cohere_rerank_calls_per_min
    if rate > 0 and _last_call_at is not None:
        wait = 60.0 / rate - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
    _last_call_at = time.monotonic()


def _call_rerank(
    query: str,
    results: list[dict[str, Any]],
    keep: int,
    model: str,
) -> list[dict[str, Any]]:
    """One Cohere rerank call; returns the top `keep` results with scores."""
    client = _get_client()
    resp = client.rerank(
        query=query,
        documents=[contextual_text(r) for r in results],   # header + text when present
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
