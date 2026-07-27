"""
AyurKosha — Parent Context Expansion
Expands selected child chunks to include surrounding parent context.

Retrieval matches on precise child chunks; generation should see the larger
parent chunk so Claude isn't handed a fragment that references "the above"
with no antecedent. This module sits between reranking/MMR (which produce
scored child chunks) and context/reorder.py + context/builder.py (which need
full parent text). It intentionally does *not* reuse
ParentStore.expand() (src/ingestion/parent_store.py) as-is: that helper
returns bare parent dicts, discarding the child's rank/score/rerank_score/
retriever fields and the original (precise) retrieval text — both of which
are still useful downstream (debugging, citation building).

Build this in: Phase 4, Step 1
"""

from __future__ import annotations

import logging
from typing import Any

from src.ingestion.parent_store import ParentStore, load_parent_store

logger = logging.getLogger(__name__)

_default_store: ParentStore | None = None


def _get_default_store() -> ParentStore:
    global _default_store
    if _default_store is None:
        _default_store = load_parent_store()
    return _default_store


def expand_to_parents(
    chunks: list[dict[str, Any]],
    store: ParentStore | None = None,
) -> list[dict[str, Any]]:
    """Replace each child chunk's text/metadata with its parent's.

    Preserves retrieval-time fields (chunk_id/rank/score/rerank_score/
    retriever) on the returned dict, and adds `retrieval_text` holding the
    original child chunk's text for reference. De-duplicates by parent_id,
    keeping the first (highest-ranked) occurrence. Chunks whose parent can't
    be found fall back to themselves unchanged (with `retrieval_text` set) so
    no context is silently dropped.

    Args:
        chunks: Scored child chunk dicts (post rerank/MMR), each with a
            `parent_id` (top-level or under `metadata`).
        store: ParentStore to look up parents in (default: lazily loaded from
            disk via load_parent_store()).

    Returns:
        Expanded chunk dicts, in the same relative order as the input's
        first occurrence of each parent.
    """
    store = store or _get_default_store()

    seen: set[str] = set()
    expanded: list[dict[str, Any]] = []
    for chunk in chunks:
        parent_id = chunk.get("parent_id") or chunk.get("metadata", {}).get("parent_id")
        parent = store.get_parent(parent_id) if parent_id else None

        if parent is None:
            logger.debug("No parent for chunk %s; using child as fallback.",
                        chunk.get("chunk_id"))
            merged = dict(chunk)
            merged["retrieval_text"] = chunk.get("text", "")
            expanded.append(merged)
            continue

        if parent_id in seen:
            continue
        seen.add(parent_id)

        merged = dict(chunk)
        merged["retrieval_text"] = chunk.get("text", "")
        merged["chunk_id"] = parent.get("chunk_id", parent_id)
        merged["text"] = parent.get("text", "")
        merged["metadata"] = parent.get("metadata", {})
        expanded.append(merged)

    logger.info("Parent expansion: %d chunks -> %d after dedup.", len(chunks), len(expanded))
    return expanded
