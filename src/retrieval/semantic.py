"""
AyurKosha — Semantic Retrieval
Dense retrieval: embed the query (input_type="search_query") and search the
Pinecone index, optionally scoped by doc_type.

Returns normalized result dicts shared across the retrieval layer:

    {"chunk_id", "text", "score", "rank", "parent_id", "metadata", "retriever"}

Supports multiple query variants (from query expansion): each variant is
searched and results are de-duplicated by chunk_id, keeping the highest score.

Optionally accepts HyDE passages (src/query/hyde.py): hypothetical answer
passages embedded as documents (input_type="search_document") and searched
alongside the query variants.

Build this in: Phase 3, Step 1
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings
from src.ingestion.embedder import embed_documents, embed_query
from src.ingestion import pinecone_store

logger = logging.getLogger(__name__)

_index = None


def _get_index():
    """Lazily fetch and cache the Pinecone index handle."""
    global _index
    if _index is None:
        _index = pinecone_store.ensure_index()
    return _index


def semantic_search(
    query: str | list[str],
    top_n: int | None = None,
    doc_type_filter: str | None = None,
    index=None,
    hyde_passages: list[str] | None = None,
) -> list[dict[str, Any]]:
    """Retrieve chunks by dense semantic similarity.

    Args:
        query: A query string, or a list of query variants (all searched;
            results merged and de-duplicated by chunk_id).
        top_n: Results per variant (default settings.semantic_retrieve_n).
        doc_type_filter: Restrict to one doc_type if given.
        index: Optional Pinecone index handle (dependency injection).
        hyde_passages: Optional hypothetical passages, embedded as documents
            and searched in addition to the query variants.

    Returns:
        Result dicts sorted by descending score, re-ranked 0..n.
    """
    top_n = top_n or settings.semantic_retrieve_n
    index = index or _get_index()
    variants = [query] if isinstance(query, str) else list(query)

    vectors = [embed_query(v) for v in variants if v and v.strip()]
    passages = [p for p in (hyde_passages or []) if p and p.strip()]
    if passages:
        vectors.extend(embed_documents(passages))

    best: dict[str, dict[str, Any]] = {}
    for vec in vectors:
        for r in pinecone_store.query(vec, top_k=top_n,
                                      doc_type_filter=doc_type_filter, index=index):
            cid = r["chunk_id"]
            r["retriever"] = "semantic"
            if cid not in best or r["score"] > best[cid]["score"]:
                best[cid] = r

    results = sorted(best.values(), key=lambda r: r["score"], reverse=True)
    for rank, r in enumerate(results):
        r["rank"] = rank
    logger.info("Semantic search: %d unique chunks across %d variant(s) + %d HyDE passage(s).",
                len(results), len(variants), len(passages))
    return results
