"""
AyurKosha — Context Reordering
Reorders selected chunks by their position in original documents.

Relevance ranking (from rerank/MMR) is not reading order — the same document
can appear multiple times at scattered ranks. Sorting by (source, page,
chunk index) groups chunks from the same document back into reading order,
which helps Claude follow the logical flow of source material instead of
seeing it shuffled.

There's no explicit integer index field on a chunk; ordinal position is
encoded in the chunk_id suffix instead (see src/ingestion/chunkers.py):
parents are "{source}_{page}_P{i}", children "..._C{j}". This module extracts
that trailing index for the sort key.

Build this in: Phase 4, Step 2
"""

from __future__ import annotations

import re
from typing import Any

_INDEX_RE = re.compile(r"_[PC](\d+)$")


def _chunk_index(chunk_id: str | None) -> int:
    """Extract the trailing _P<n>/_C<n> ordinal from a chunk_id (0 if absent)."""
    if not chunk_id:
        return 0
    m = _INDEX_RE.search(chunk_id)
    return int(m.group(1)) if m else 0


def reorder_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sort chunks into (source_document, page, chunk_index) reading order.

    Args:
        chunks: Chunk dicts with a `metadata` dict (source/page) and
            `chunk_id`.

    Returns:
        The same chunks, stably sorted into reading order.
    """
    def sort_key(chunk: dict[str, Any]) -> tuple[str, int, int]:
        meta = chunk.get("metadata", {})
        source = meta.get("source") or ""
        page = meta.get("page") or 0
        return (source, page, _chunk_index(chunk.get("chunk_id")))

    return sorted(chunks, key=sort_key)
