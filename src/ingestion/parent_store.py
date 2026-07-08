"""
AyurKosha — Parent-Child Chunk Mapping
Stores the large parent chunks and maps a retrieved child chunk back to its
parent context.

Retrieval matches small, precise child chunks; generation is fed the larger
parent chunk (Parent-Child / Hierarchical Retrieval pattern) so Claude sees
complete context instead of a fragment that references "the above". This store
is the parent_id -> parent-chunk lookup that makes that expansion possible.

Artifact: data/cache/parent_store.json (JSON; parents are plain text +
JSON-serializable metadata).

Build this in: Phase 2, Step 8
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORE_PATH = PROJECT_ROOT / "data" / "cache" / "parent_store.json"


class ParentStore:
    """In-memory parent_id -> parent chunk lookup with JSON persistence."""

    def __init__(self, parents: dict[str, dict[str, Any]] | None = None):
        self._parents: dict[str, dict[str, Any]] = parents or {}

    def __len__(self) -> int:
        return len(self._parents)

    def __contains__(self, parent_id: str) -> bool:
        return parent_id in self._parents

    def get_parent(self, parent_id: str) -> dict[str, Any] | None:
        """Return the parent chunk for an id, or None if unknown."""
        return self._parents.get(parent_id)

    def get_parent_text(self, parent_id: str) -> str | None:
        """Convenience: return just the parent's text, or None."""
        parent = self._parents.get(parent_id)
        return parent.get("text") if parent else None

    def expand(self, child_chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Map retrieved child chunks to their parent chunks.

        De-duplicates by parent_id (multiple children can share one parent),
        preserving first-seen order. Children whose parent is missing fall back
        to the child itself so no context is silently dropped.
        """
        seen: set[str] = set()
        expanded: list[dict[str, Any]] = []
        for child in child_chunks:
            parent_id = child.get("parent_id") or child.get("metadata", {}).get("parent_id")
            if parent_id and parent_id in self._parents:
                if parent_id in seen:
                    continue
                seen.add(parent_id)
                expanded.append(self._parents[parent_id])
            else:
                logger.debug("No parent for child %s; using child as fallback.",
                             child.get("chunk_id"))
                expanded.append(child)
        return expanded


def build_parent_store(parents: list[dict[str, Any]]) -> ParentStore:
    """Build a ParentStore from parent chunk dicts (from chunkers.chunk_records)."""
    mapping: dict[str, dict[str, Any]] = {}
    for parent in parents:
        pid = parent.get("chunk_id")
        if not pid:
            continue
        mapping[pid] = {
            "chunk_id": pid,
            "text": parent.get("text", ""),
            "metadata": parent.get("metadata", {}),
        }
    logger.info("Built parent store with %d parents.", len(mapping))
    return ParentStore(mapping)


def save_parent_store(store: ParentStore, path: str | Path = DEFAULT_STORE_PATH) -> Path:
    """Serialize a ParentStore to JSON. Creates parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(store._parents, f, ensure_ascii=False)
    logger.info("Saved parent store (%d parents) to %s.", len(store), path)
    return path


def load_parent_store(path: str | Path = DEFAULT_STORE_PATH) -> ParentStore:
    """Load a ParentStore from JSON.

    Raises:
        FileNotFoundError: if the store has not been built yet.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Parent store not found at {path}. Run ingestion first."
        )
    with open(path, "r", encoding="utf-8") as f:
        parents = json.load(f)
    logger.info("Loaded parent store (%d parents) from %s.", len(parents), path)
    return ParentStore(parents)
