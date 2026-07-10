"""Tests for src/retrieval/fusion.py (Reciprocal Rank Fusion).

Run: python -m pytest tests/test_fusion.py
"""

from src.retrieval.fusion import reciprocal_rank_fusion


def _mk(cid, retriever):
    return {"chunk_id": cid, "text": f"text-{cid}", "retriever": retriever,
            "metadata": {}}


def test_rrf_rewards_agreement():
    # 'b' is ranked highly by BOTH retrievers -> should win.
    semantic = [_mk("a", "semantic"), _mk("b", "semantic"), _mk("c", "semantic")]
    keyword = [_mk("b", "keyword"), _mk("d", "keyword"), _mk("a", "keyword")]
    fused = reciprocal_rank_fusion([semantic, keyword], k=60)
    assert fused[0]["chunk_id"] == "b"
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_rrf_records_retrievers():
    semantic = [_mk("a", "semantic")]
    keyword = [_mk("a", "keyword")]
    fused = reciprocal_rank_fusion([semantic, keyword])
    assert set(fused[0]["retrievers"]) == {"semantic", "keyword"}


def test_rrf_dedupes_and_ranks():
    semantic = [_mk("a", "semantic"), _mk("b", "semantic")]
    keyword = [_mk("a", "keyword"), _mk("c", "keyword")]
    fused = reciprocal_rank_fusion([semantic, keyword])
    ids = [f["chunk_id"] for f in fused]
    assert sorted(ids) == ["a", "b", "c"]      # unique
    assert [f["rank"] for f in fused] == [0, 1, 2]


def test_rrf_top_n_truncates():
    lists = [[_mk(str(i), "semantic") for i in range(10)]]
    fused = reciprocal_rank_fusion(lists, top_n=3)
    assert len(fused) == 3


def test_rrf_k_affects_scores():
    lists = [[_mk("a", "semantic")]]
    low_k = reciprocal_rank_fusion(lists, k=1)[0]["rrf_score"]
    high_k = reciprocal_rank_fusion(lists, k=1000)[0]["rrf_score"]
    assert low_k > high_k  # smaller k -> larger reciprocal


def test_rrf_empty():
    assert reciprocal_rank_fusion([]) == []
    assert reciprocal_rank_fusion([[], []]) == []
