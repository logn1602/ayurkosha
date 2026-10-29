"""Tests for src/reranking/mmr.py (pure MMR selection — no API).

cohere_rerank.py requires the live Cohere API and is exercised by the Phase-3
end-to-end run rather than here.

Run: python -m pytest tests/test_reranking.py
"""

from src.reranking.mmr import mmr


def test_mmr_picks_most_relevant_first():
    query = [1.0, 0.0]
    cands = [
        [0.2, 1.0],   # 0: not aligned with query
        [1.0, 0.0],   # 1: perfectly aligned
        [0.9, 0.1],   # 2: nearly aligned
    ]
    order = mmr(query, cands, lambda_mult=0.7, top_k=1)
    assert order == [1]


def test_mmr_prefers_diversity_over_near_duplicate():
    query = [1.0, 0.0]
    cands = [
        [1.0, 0.0],    # 0: best relevance
        [0.99, 0.01],  # 1: near-duplicate of 0
        [0.0, 1.0],    # 2: orthogonal (diverse)
    ]
    # After picking 0, a diversity-dominant pass (lambda < 0.5) should prefer
    # the orthogonal candidate 2 over the near-duplicate 1. (At lambda=0.5 the
    # two tie exactly, so we weight diversity to make the intent explicit.)
    order = mmr(query, cands, lambda_mult=0.3, top_k=2)
    assert order[0] == 0
    assert order[1] == 2


def test_mmr_high_lambda_ignores_diversity():
    query = [1.0, 0.0]
    cands = [
        [1.0, 0.0],    # 0
        [0.98, 0.02],  # 1: near-duplicate, 2nd most relevant
        [0.0, 1.0],    # 2: diverse but low relevance
    ]
    order = mmr(query, cands, lambda_mult=1.0, top_k=2)
    assert order == [0, 1]  # pure relevance -> the near-duplicate wins slot 2


def test_mmr_top_k_bounded_by_candidates():
    order = mmr([1.0, 0.0], [[1.0, 0.0], [0.0, 1.0]], top_k=10)
    assert len(order) == 2
    assert sorted(order) == [0, 1]


def test_mmr_empty():
    assert mmr([1.0, 0.0], [], top_k=5) == []


# ── MMR relevance = rerank score ──────────────────────────────────────

def test_mmr_relevance_scores_override_query_cosine():
    query = [1.0, 0.0]
    cands = [[0.0, 1.0], [1.0, 0.0]]          # cosine prefers candidate 1
    order = mmr(query, cands, top_k=1, relevance=[0.9, 0.1])
    assert order == [0]


def test_mmr_rerank_first_pick_is_always_rerank_rank1(monkeypatch):
    """Even when the rank-1 passage is the *least* similar to the query by
    embedding, MMR must keep it first once rerank scores are present."""
    from src.ingestion import embedder
    from src.reranking import mmr as mmr_mod

    vecs = {"a": [0.0, 1.0], "b": [1.0, 0.0], "c": [0.9, 0.1], "d": [0.8, 0.2]}
    monkeypatch.setattr(embedder, "embed_documents", lambda texts: [vecs[t] for t in texts])
    monkeypatch.setattr(embedder, "embed_query",
                        lambda q: (_ for _ in ()).throw(AssertionError("no query embed needed")))
    reranked = [{"chunk_id": t, "text": t, "rerank_score": s}
                for t, s in [("a", 0.95), ("b", 0.60), ("c", 0.55), ("d", 0.50)]]
    out = mmr_mod.mmr_rerank("q", reranked, top_k=2)
    assert out[0]["chunk_id"] == "a"
    assert out[0]["rank"] == 0


def test_mmr_rerank_falls_back_to_query_cosine_without_rerank_scores(monkeypatch):
    from src.ingestion import embedder
    from src.reranking import mmr as mmr_mod

    vecs = {"a": [0.0, 1.0], "b": [1.0, 0.0], "c": [0.9, 0.1]}
    monkeypatch.setattr(embedder, "embed_documents", lambda texts: [vecs[t] for t in texts])
    monkeypatch.setattr(embedder, "embed_query", lambda q: [1.0, 0.0])
    results = [{"chunk_id": t, "text": t} for t in "abc"]
    out = mmr_mod.mmr_rerank("q", results, top_k=2)
    assert out[0]["chunk_id"] == "b"
