"""
AyurKosha — Keyword Retrieval (BM25)
Sparse retrieval over the serialized BM25 index, using the Ayurvedic tokenizer
(synonym expansion + Devanagari + stemming) so "Amla" matches "Amalaki".

Returns the same normalized result dicts as semantic.py:

    {"chunk_id", "text", "score", "rank", "parent_id", "metadata", "retriever"}

Supports multiple query variants; results are de-duplicated by chunk_id,
keeping the highest BM25 score.

Build this in: Phase 3, Step 2
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings
from src.ingestion import bm25_store

logger = logging.getLogger(__name__)

_index = None


def _get_index():
    """Lazily load and cache the BM25 index from disk."""
    global _index
    if _index is None:
        _index = bm25_store.load_bm25_index()
    return _index


def keyword_search(
    query: str | list[str],
    top_n: int | None = None,
    index=None,
) -> list[dict[str, Any]]:
    """Retrieve chunks by BM25 keyword scoring.

    Args:
        query: A query string, or a list of query variants.
        top_n: Results per variant (default settings.bm25_retrieve_n).
        index: Optional BM25Index (dependency injection).

    Returns:
        Result dicts sorted by descending score, re-ranked 0..n.
    """
    top_n = top_n or settings.bm25_retrieve_n
    index = index or _get_index()
    variants = [query] if isinstance(query, str) else list(query)

    best: dict[str, dict[str, Any]] = {}
    for variant in variants:
        if not variant or not variant.strip():
            continue
        for r in index.search(variant, top_n=top_n):
            cid = r["chunk_id"]
            r["retriever"] = "keyword"
            if cid not in best or r["score"] > best[cid]["score"]:
                best[cid] = r

    results = sorted(best.values(), key=lambda r: r["score"], reverse=True)
    for rank, r in enumerate(results):
        r["rank"] = rank
    logger.info("Keyword search: %d unique chunks across %d variant(s).",
                len(results), len(variants))
    return results
