"""
AyurKosha — Reciprocal Rank Fusion (RRF)
Merges the ranked lists from the semantic and keyword retrievers into a single
ranking without needing to normalize their incompatible score scales.

    RRF_score(chunk) = Σ  1 / (k + rank_in_list)     over all lists it appears in

`rank_in_list` is 1-indexed (best result = rank 1). k (default 60, from
settings) dampens the influence of very high ranks. A chunk both retrievers
agree on accumulates score from both lists and rises to the top.

Build this in: Phase 3, Step 3
"""

from __future__ import annotations

import logging
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)


def reciprocal_rank_fusion(
    result_lists: list[list[dict[str, Any]]],
    k: int | None = None,
    top_n: int | None = None,
) -> list[dict[str, Any]]:
    """Fuse multiple ranked result lists via Reciprocal Rank Fusion.

    Args:
        result_lists: Lists of result dicts (each already ordered best-first).
            Each dict must have a ``chunk_id``.
        k: RRF constant (default settings.rrf_k).
        top_n: Truncate the fused list to this many results (default: all).

    Returns:
        Fused result dicts with an added ``rrf_score`` and a recomputed
        ``rank`` (0-indexed), sorted by descending rrf_score. The other fields
        (text/metadata/parent_id) are taken from the first list in which each
        chunk appears; a ``retrievers`` list records which retrievers hit it.
    """
    k = k or settings.rrf_k
    scores: dict[str, float] = {}
    payloads: dict[str, dict[str, Any]] = {}
    retrievers: dict[str, list[str]] = {}

    for results in result_lists:
        for position, r in enumerate(results):
            cid = r.get("chunk_id")
            if cid is None:
                continue
            rank_in_list = position + 1  # 1-indexed
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank_in_list)
            if cid not in payloads:
                payloads[cid] = r
                retrievers[cid] = []
            src = r.get("retriever")
            if src and src not in retrievers[cid]:
                retrievers[cid].append(src)

    fused: list[dict[str, Any]] = []
    for cid in sorted(scores, key=lambda c: scores[c], reverse=True):
        item = dict(payloads[cid])
        item["rrf_score"] = scores[cid]
        item["retrievers"] = retrievers[cid]
        fused.append(item)

    if top_n is not None:
        fused = fused[:top_n]
    for rank, item in enumerate(fused):
        item["rank"] = rank

    logger.info("RRF fused %d lists -> %d unique chunks (returning %d).",
                len(result_lists), len(scores), len(fused))
    return fused
