"""
AyurKosha — Chunking Strategies
Structure-aware, parent-child chunking for Ayurvedic texts.

Implements the Parent-Child (Hierarchical Retrieval) pattern:

    PARENT chunk  — large window (~1600 chars). Full context; fed to Claude.
    CHILD chunk   — small window (~450 chars, overlapping). Precise; embedded
                    and BM25-indexed; what we actually retrieve on.

At query time we match child chunks (better precision) then expand to their
parent (better context) via parent_store.

Splitting is a dependency-free recursive character splitter that respects a
separator hierarchy (paragraph -> line -> sentence -> word -> hard cut). This
is deliberate: the classical-text scans are OCR-noisy and lack reliable
shloka delimiters, so true verse-level segmentation is not recoverable from
them. Structural signal that *is* recoverable (text_name, sthana, chapter,
monograph sections, drug properties) is already captured by metadata.py and
propagated onto every chunk here.

Chunk record schemas:

    parent = {"chunk_id", "text", "metadata"{..., "is_parent": True}}
    child  = {"chunk_id", "parent_id", "text",
              "metadata"{..., "parent_id", "is_parent": False}}

chunk_records() returns {"parents": [...], "children": [...]}.

Build this in: Phase 2, Step 3
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Sizes in characters (~4 chars/token). Tune from eval results later.
PARENT_CHUNK_SIZE = 1600
PARENT_OVERLAP = 0
CHILD_CHUNK_SIZE = 450
CHILD_OVERLAP = 80

# Separator hierarchy: try to split on the most semantic boundary first.
_SEPARATORS = ["\n\n", "\n", ". ", "; ", ", ", " "]

_ID_SANITIZE_RE = re.compile(r"[^A-Za-z0-9]+")


def _sanitize_id(text: str) -> str:
    """Make an ASCII-safe, Pinecone-friendly id fragment."""
    return _ID_SANITIZE_RE.sub("_", text).strip("_")


def _hard_split(unit: str, size: int) -> list[str]:
    """Split an oversize unit that has no usable separators into <= size pieces."""
    return [unit[i:i + size] for i in range(0, len(unit), size)]


def _atomic_units(text: str, size: int, separators: list[str]) -> list[str]:
    """Break text into units each <= `size`, descending the separator hierarchy."""
    text = text.strip()
    if not text:
        return []
    if len(text) <= size:
        return [text]
    if not separators:
        return _hard_split(text, size)

    sep, rest = separators[0], separators[1:]
    parts = text.split(sep)
    units: list[str] = []
    for part in parts:
        part = part.strip()
        if not part:
            continue
        if len(part) <= size:
            units.append(part)
        else:
            units.extend(_atomic_units(part, size, rest))
    return units


def _tail_overlap(chunk: str, overlap: int) -> str:
    """Return up to `overlap` trailing characters of `chunk`, cut at a space."""
    if overlap <= 0 or len(chunk) <= overlap:
        return chunk if overlap > 0 else ""
    tail = chunk[-overlap:]
    space = tail.find(" ")
    return tail[space + 1:] if space != -1 else tail


def split_text(text: str, chunk_size: int, overlap: int = 0) -> list[str]:
    """Split text into overlapping chunks of at most `chunk_size` characters.

    Greedily packs atomic units up to the size limit, seeding each new chunk
    with the tail `overlap` characters of the previous one (cut on a word
    boundary). Deterministic and dependency-free.
    """
    units = _atomic_units(text, chunk_size, _SEPARATORS)
    if not units:
        return []

    chunks: list[str] = []
    current = ""
    for unit in units:
        if not current:
            current = unit
            continue
        # +1 for the joining space.
        if len(current) + 1 + len(unit) <= chunk_size:
            current = f"{current} {unit}"
        else:
            chunks.append(current)
            seed = _tail_overlap(current, overlap)
            current = f"{seed} {unit}".strip() if seed else unit
    if current:
        chunks.append(current)
    return chunks


def _child_metadata(base: dict[str, Any], parent_id: str, child_id: str) -> dict[str, Any]:
    meta = dict(base)
    meta["chunk_id"] = child_id
    meta["parent_id"] = parent_id
    meta["is_parent"] = False
    return meta


def _parent_metadata(base: dict[str, Any], parent_id: str) -> dict[str, Any]:
    meta = dict(base)
    meta["chunk_id"] = parent_id
    meta["is_parent"] = True
    return meta


def chunk_record(record: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Split one enriched loader record into parent and child chunks.

    Returns {"parents": [...], "children": [...]}.
    """
    text = record.get("text", "")
    base_meta = record.get("metadata", {})
    if not text.strip():
        return {"parents": [], "children": []}

    source = base_meta.get("source", "doc")
    page = base_meta.get("page")
    id_stem = _sanitize_id(f"{source}_{page}" if page is not None else source)

    parents: list[dict[str, Any]] = []
    children: list[dict[str, Any]] = []

    parent_texts = split_text(text, PARENT_CHUNK_SIZE, PARENT_OVERLAP)
    for pi, parent_text in enumerate(parent_texts):
        parent_id = f"{id_stem}_P{pi}"
        parents.append({
            "chunk_id": parent_id,
            "text": parent_text,
            "metadata": _parent_metadata(base_meta, parent_id),
        })

        child_texts = split_text(parent_text, CHILD_CHUNK_SIZE, CHILD_OVERLAP)
        for ci, child_text in enumerate(child_texts):
            child_id = f"{parent_id}_C{ci}"
            children.append({
                "chunk_id": child_id,
                "parent_id": parent_id,
                "text": child_text,
                "metadata": _child_metadata(base_meta, parent_id, child_id),
            })

    return {"parents": parents, "children": children}


def chunk_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Chunk a list of enriched records into corpus-wide parent/child lists.

    Chunk ids are unique across the corpus (derived from source + page +
    positional indices). Records that fail to chunk are logged and skipped.
    """
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for record in records:
        try:
            result = chunk_record(record)
        except Exception as exc:
            logger.warning("Chunking failed for %s: %s",
                           record.get("metadata", {}).get("source"), exc)
            continue
        all_parents.extend(result["parents"])
        all_children.extend(result["children"])

    logger.info("Chunked %d records -> %d parents, %d children.",
                len(records), len(all_parents), len(all_children))
    return {"parents": all_parents, "children": all_children}
