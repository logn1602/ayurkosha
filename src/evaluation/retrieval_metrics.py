"""
AyurKosha — Retrieval Quality Metrics
Measures Recall@k, MRR, Precision@k against a gold standard.

The eval dataset's ``gold_sources`` are *work-level* labels (e.g.
"charaka-chikitsa-ch29", "afi-vol1", "api-vol1-monograph") — they name a
classical work / pharmacopoeia volume, not an exact chunk_id. So retrieval
relevance here is judged at the **work level**: a retrieved chunk is
"relevant" to a gold source when both normalize to the same canonical work
title. Normalization reuses the same filename-keyword mapping the ingestion
layer uses (src/ingestion/metadata.py::infer_text_name), so gold labels and
chunk ``source`` filenames land on identical keys.

The three metric functions are pure and operate on ranked lists of string
keys + a set of relevant keys — unit-tested with no API calls.

Build this in: Phase 6
"""

from __future__ import annotations

from typing import Any

from src.ingestion.metadata import TEXT_NAME_BY_KEYWORD, infer_text_name

# Reverse lookup: lowercased canonical title -> canonical title. Lets work_key
# recognize an already-canonical name (a chunk's text_name), not just a
# filename/label keyword — so the gold side ("api-vol1-monograph" -> title via
# infer_text_name) and the chunk side (text_name already the title) converge on
# the same key instead of one falling back to lowercase.
_CANONICAL_BY_LOWER = {name.lower(): name for _, name in TEXT_NAME_BY_KEYWORD}


def work_key(label: str | None) -> str:
    """Normalize a gold-source label or chunk source to a canonical work key.

    Tries filename/label keyword inference first, then an exact (case-
    insensitive) canonical-title match. Falls back to the lowercased label
    when neither matches, so unrecognized sources still compare consistently
    (they just won't collide with a canonical title).
    """
    if not label:
        return ""
    name = infer_text_name(label)
    if name:
        return name
    lowered = label.strip().lower()
    return _CANONICAL_BY_LOWER.get(lowered, lowered)


def chunk_work_key(chunk: dict[str, Any]) -> str:
    """Work key for a retrieved chunk: prefer its text_name, else its source."""
    meta = chunk.get("metadata", {})
    return work_key(meta.get("text_name") or meta.get("source"))


def relevant_keys(gold_sources: list[str]) -> set[str]:
    """Canonical work keys for a question's gold sources."""
    return {work_key(g) for g in gold_sources if g}


def recall_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of relevant keys that appear in the top-k retrieved keys.

    Returns 0.0 when there are no relevant keys (nothing to recall).
    """
    if not relevant:
        return 0.0
    top_k = set(retrieved[:k])
    return len(relevant & top_k) / len(relevant)


def precision_at_k(retrieved: list[str], relevant: set[str], k: int) -> float:
    """Fraction of the top-k retrieved keys that are relevant.

    Denominator is min(k, len(retrieved)) so a short result list isn't
    penalized for positions that never existed. Returns 0.0 on empty input.
    """
    if not retrieved or k <= 0:
        return 0.0
    window = retrieved[:k]
    denom = len(window)
    hits = sum(1 for key in window if key in relevant)
    return hits / denom if denom else 0.0


def mrr(retrieved: list[str], relevant: set[str]) -> float:
    """Reciprocal rank (1/rank, 1-indexed) of the first relevant key, else 0.0."""
    for i, key in enumerate(retrieved, start=1):
        if key in relevant:
            return 1.0 / i
    return 0.0


def score_retrieval(
    retrieved_chunks: list[dict[str, Any]],
    gold_sources: list[str],
    k: int,
) -> dict[str, float]:
    """Compute all retrieval metrics for one question's ranked chunk list.

    Args:
        retrieved_chunks: Ranked result dicts (best-first) with metadata.
        gold_sources: The question's gold_sources labels.
        k: Cutoff for recall@k / precision@k.

    Returns:
        {"recall_at_k", "precision_at_k", "mrr", "hit"} where ``hit`` is 1.0
        if any gold work was retrieved in the top-k at all.
    """
    retrieved_keys = [chunk_work_key(c) for c in retrieved_chunks]
    relevant = relevant_keys(gold_sources)
    recall = recall_at_k(retrieved_keys, relevant, k)
    return {
        "recall_at_k": recall,
        "precision_at_k": precision_at_k(retrieved_keys, relevant, k),
        "mrr": mrr(retrieved_keys, relevant),
        "hit": 1.0 if recall > 0 else 0.0,
    }
