"""
AyurKosha — BM25 Index Management
Builds, serializes, and loads the sparse keyword (BM25) index over child chunks.

The index tokenizes every child chunk with the Ayurvedic tokenizer
(synonym expansion + Devanagari + stemming), so a query for "Amla" matches a
chunk that only says "Amalaki". The serialized artifact bundles the fitted
BM25Okapi model together with the chunk payloads needed to map a hit back to
its text/metadata, so retrieval can run entirely from the saved index with no
document re-processing.

Artifact: data/cache/bm25_index.pkl (pickle).

Build this in: Phase 2, Step 7
"""

from __future__ import annotations

import logging
import pickle
from pathlib import Path
from typing import Any

from src.retrieval.tokenizer import tokenize_ayurvedic

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_INDEX_PATH = PROJECT_ROOT / "data" / "cache" / "bm25_index.pkl"


class BM25Index:
    """A fitted BM25 model plus the chunk payloads it was built from."""

    def __init__(self, bm25: Any, chunks: list[dict[str, Any]]):
        self._bm25 = bm25
        # Store only what retrieval needs to return, in corpus order.
        self.chunks = chunks

    def __len__(self) -> int:
        return len(self.chunks)

    def search(self, query: str, top_n: int = 50) -> list[dict[str, Any]]:
        """Return the top-N chunks for a query, each with a bm25 score.

        Results are ordered by descending score. Zero-score hits are excluded.
        """
        if not self.chunks:
            return []
        query_tokens = tokenize_ayurvedic(query)
        if not query_tokens:
            return []
        scores = self._bm25.get_scores(query_tokens)
        ranked = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        results: list[dict[str, Any]] = []
        for rank, idx in enumerate(ranked[:top_n]):
            score = float(scores[idx])
            if score <= 0.0:
                break
            chunk = dict(self.chunks[idx])
            chunk["score"] = score
            chunk["rank"] = rank
            results.append(chunk)
        return results


def build_bm25_index(children: list[dict[str, Any]]) -> BM25Index:
    """Build a BM25Index from child chunks.

    Args:
        children: Child chunk dicts (from chunkers.chunk_records) with at least
            ``chunk_id``, ``text``, and ``metadata``.

    Returns:
        A fitted BM25Index.

    Raises:
        ImportError: if rank_bm25 is not installed.
        ValueError: if no usable chunks are provided.
    """
    try:
        from rank_bm25 import BM25Okapi
    except ImportError as exc:
        raise ImportError(
            "rank_bm25 is required to build the BM25 index. "
            "Install it with: pip install rank-bm25"
        ) from exc

    corpus_tokens: list[list[str]] = []
    payloads: list[dict[str, Any]] = []
    for chunk in children:
        text = chunk.get("text", "")
        tokens = tokenize_ayurvedic(text)
        if not tokens:
            continue
        corpus_tokens.append(tokens)
        payloads.append({
            "chunk_id": chunk.get("chunk_id"),
            "parent_id": chunk.get("parent_id"),
            "text": text,
            "metadata": chunk.get("metadata", {}),
        })

    if not corpus_tokens:
        raise ValueError("No tokenizable chunks provided to build_bm25_index.")

    bm25 = BM25Okapi(corpus_tokens)
    logger.info("Built BM25 index over %d chunks.", len(payloads))
    return BM25Index(bm25, payloads)


def save_bm25_index(index: BM25Index, path: str | Path = DEFAULT_INDEX_PATH) -> Path:
    """Pickle a BM25Index to disk. Creates parent directories as needed."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(index, f, protocol=pickle.HIGHEST_PROTOCOL)
    logger.info("Saved BM25 index (%d chunks) to %s.", len(index), path)
    return path


def load_bm25_index(path: str | Path = DEFAULT_INDEX_PATH) -> BM25Index:
    """Load a BM25Index from disk.

    Raises:
        FileNotFoundError: if the index has not been built yet.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"BM25 index not found at {path}. Run ingestion first."
        )
    with open(path, "rb") as f:
        index = pickle.load(f)
    logger.info("Loaded BM25 index (%d chunks) from %s.", len(index), path)
    return index
