"""
AyurKosha — Retrieval Quality Metrics
Measures Recall@k, MRR, Precision@k against a gold standard.

The eval dataset's ``gold_works`` are *work-level* labels (e.g.
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

import re
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


def relevant_keys(gold_works: list[str]) -> set[str]:
    """Canonical work keys for a question's gold works."""
    return {work_key(g) for g in gold_works if g}


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
    gold_works: list[str],
    k: int,
) -> dict[str, float]:
    """Compute all retrieval metrics for one question's ranked chunk list.

    Args:
        retrieved_chunks: Ranked result dicts (best-first) with metadata.
        gold_works: The question's work-level gold labels.
        k: Cutoff for recall@k / precision@k.

    Returns:
        {"recall_at_k", "precision_at_k", "mrr", "mrr_at_k", "hit"}:
          - ``hit`` is 1.0 if any gold work is in the top-k;
          - ``mrr_at_k`` is the reciprocal rank of the first gold work within
            the top-k (0 past the cutoff): the same cutoff for every pipeline,
            and the headline MRR;
          - ``mrr`` uses the whole scored list, 15 deep for rrf/rerank (MRR@15)
            but only k deep for rerank_mmr, so it isn't comparable across them.
    """
    retrieved_keys = [chunk_work_key(c) for c in retrieved_chunks]
    relevant = relevant_keys(gold_works)
    recall = recall_at_k(retrieved_keys, relevant, k)
    return {
        "recall_at_k": recall,
        "precision_at_k": precision_at_k(retrieved_keys, relevant, k),
        "mrr": mrr(retrieved_keys, relevant),
        "mrr_at_k": mrr(retrieved_keys[:k], relevant),
        "hit": 1.0 if recall > 0 else 0.0,
    }


# ── passage level ─────────────────────────────────────────────────────
# Work-level relevance is the lenient bound: any chunk of a gold work counts.
# Passage level is the strict bound: a retrieved chunk is a hit only if its
# parent is one of the question's gold passages (``gold_passages``), or it
# lies within PASSAGE_PAGE_WINDOW pages of one in the same source file. Page
# numbers restart per file (Sushruta vol 1 p535 is not vol 2 p535), so "same
# work" means same file.

PASSAGE_PAGE_WINDOW = 1
# The Formulary prints two columns with different formulations side by side, so
# an adjacent page is another formulation: its passages get no page allowance
# (the passage's own page still counts, since parent ids shift when pages are
# re-chunked).
PASSAGE_PAGE_WINDOW_BY_WORK = {"Ayurvedic Formulary of India": 0}
_SUPPORT_ID_RE = re.compile(r"^(?P<stem>.+)_(?P<page>\d+)_P\d+$")
_CHILD_SUFFIX_RE = re.compile(r"_C\d+$")
_ID_UNSAFE_RE = re.compile(r"[^A-Za-z0-9]+")      # as chunkers._sanitize_id


def _source_stem(source: str | None) -> str:
    return _ID_UNSAFE_RE.sub("_", source or "").strip("_")


def parse_support_id(parent_id: str) -> tuple[str, int] | None:
    """("api_all_volume_pdf", 40) from "api_all_volume_pdf_40_P0", or None."""
    m = _SUPPORT_ID_RE.match(parent_id or "")
    return (m.group("stem"), int(m.group("page"))) if m else None


def _chunk_parent_id(chunk: dict[str, Any]) -> str | None:
    parent = chunk.get("parent_id") or (chunk.get("metadata") or {}).get("parent_id")
    if parent:
        return parent
    cid = chunk.get("chunk_id") or ""
    return _CHILD_SUFFIX_RE.sub("", cid) if _CHILD_SUFFIX_RE.search(cid) else None


def covered_passages(chunk: dict[str, Any], supporting_ids: list[str],
                     window: int = PASSAGE_PAGE_WINDOW) -> set[str]:
    """The supporting passages a retrieved chunk counts as hitting."""
    meta = chunk.get("metadata") or {}
    parent, stem, page = _chunk_parent_id(chunk), _source_stem(meta.get("source")), meta.get("page")
    page = int(float(page)) if page is not None else None
    covered = set()
    for pid in supporting_ids:
        parsed = parse_support_id(pid)
        if parent == pid:
            covered.add(pid)
        elif parsed and page is not None and stem == parsed[0]:
            allowed = min(window, PASSAGE_PAGE_WINDOW_BY_WORK.get(work_key(parsed[0]), window))
            if abs(page - parsed[1]) <= allowed:
                covered.add(pid)
    return covered


def first_passage_rank(retrieved_chunks: list[dict[str, Any]], supporting_ids: list[str]) -> int | None:
    """1-based rank of the first retrieved chunk that hits a supporting passage, or None."""
    for rank, chunk in enumerate(retrieved_chunks, start=1):
        if covered_passages(chunk, supporting_ids):
            return rank
    return None


def score_passages(
    retrieved_chunks: list[dict[str, Any]],
    supporting_ids: list[str],
    k: int,
) -> dict[str, float] | None:
    """Passage-level {"hit", "recall_at_k", "mrr_at_k"}; None without supporting ids.

    ``recall_at_k`` is the share of supporting passages covered by the top-k,
    so it is capped at k / len(supporting_ids) for large supporting sets.
    """
    if not supporting_ids:
        return None
    top = retrieved_chunks[:k]
    covered = set().union(*(covered_passages(c, supporting_ids) for c in top)) if top else set()
    first = first_passage_rank(top, supporting_ids)
    return {
        "hit": 1.0 if covered else 0.0,
        "recall_at_k": len(covered) / len(set(supporting_ids)),
        "mrr_at_k": 1.0 / first if first else 0.0,
    }
