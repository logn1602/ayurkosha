"""
AyurKosha — Maximal Marginal Relevance (MMR)
Final diversity pass. After reranking gives the most relevant passages, MMR
picks the final top-k so they aren't near-duplicates of each other — e.g. six
slightly different snippets of the same monograph paragraph. This widens the
evidence Claude sees.

Selection rule, iterated until k chosen:

    next = argmax_{d not selected}  [ λ · sim(d, query)
                                      − (1 − λ) · max_{s selected} sim(d, s) ]

λ (lambda_mult) trades relevance (high λ) against diversity (low λ); default
0.7 favours relevance with some diversity.

`mmr()` is a pure function over vectors (unit-tested). `mmr_rerank()` is the
convenience wrapper that embeds candidate texts + the query, then applies it.

Build this in: Phase 3, Step 5
"""

from __future__ import annotations

import logging
from typing import Any

import numpy as np

from config.settings import settings

logger = logging.getLogger(__name__)

DEFAULT_LAMBDA = 0.7


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    denom = (np.linalg.norm(a) * np.linalg.norm(b))
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def mmr(
    query_vec: list[float],
    candidate_vecs: list[list[float]],
    lambda_mult: float = DEFAULT_LAMBDA,
    top_k: int = 6,
) -> list[int]:
    """Select diverse-yet-relevant candidate indices via MMR.

    Args:
        query_vec: Query embedding.
        candidate_vecs: Candidate embeddings (same space as query_vec).
        lambda_mult: Relevance/diversity trade-off in [0, 1].
        top_k: Number of indices to select.

    Returns:
        Selected candidate indices, in selection order.
    """
    if not candidate_vecs:
        return []
    q = np.asarray(query_vec, dtype=float)
    cands = [np.asarray(v, dtype=float) for v in candidate_vecs]
    sim_to_query = [_cosine(q, c) for c in cands]

    selected: list[int] = []
    remaining = list(range(len(cands)))
    k = min(top_k, len(cands))

    while remaining and len(selected) < k:
        if not selected:
            best = max(remaining, key=lambda i: sim_to_query[i])
        else:
            def mmr_score(i: int) -> float:
                max_sim_selected = max(_cosine(cands[i], cands[j]) for j in selected)
                return lambda_mult * sim_to_query[i] - (1 - lambda_mult) * max_sim_selected
            best = max(remaining, key=mmr_score)
        selected.append(best)
        remaining.remove(best)
    return selected


def mmr_rerank(
    query: str,
    results: list[dict[str, Any]],
    lambda_mult: float = DEFAULT_LAMBDA,
    top_k: int | None = None,
) -> list[dict[str, Any]]:
    """Apply MMR diversity selection to reranked results.

    Embeds candidate texts (search_document) and the query (search_query) to
    get vectors, then selects a diverse top_k. If there are already <= top_k
    candidates, returns them unchanged (no embedding cost).

    Args:
        query: The user query.
        results: Reranked result dicts with ``text`` fields.
        lambda_mult: Relevance/diversity trade-off.
        top_k: Final passage count (default settings.top_k_final).

    Returns:
        The selected result dicts (<= top_k), with recomputed ``rank``.
    """
    top_k = top_k or settings.top_k_final
    if len(results) <= top_k:
        return results

    from src.ingestion.embedder import embed_documents, embed_query

    cand_vecs = [r.get("embedding") for r in results]
    if not all(cand_vecs):  # embed any missing vectors
        cand_vecs = embed_documents([r.get("text", "") for r in results])
    query_vec = embed_query(query)

    idxs = mmr(query_vec, cand_vecs, lambda_mult=lambda_mult, top_k=top_k)
    selected = [results[i] for i in idxs]
    for rank, r in enumerate(selected):
        r["rank"] = rank
    logger.info("MMR: %d candidates -> %d diverse passages (lambda=%.2f).",
                len(results), len(selected), lambda_mult)
    return selected
