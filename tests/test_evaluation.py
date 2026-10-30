"""Tests for src/evaluation/ pure metric functions (no API).

The LLM judge (llm_judge.py) needs the live Anthropic API and is exercised by
an actual eval run rather than here.

Run: python -m pytest tests/test_evaluation.py
"""

from src.evaluation.generation_metrics import (
    citation_accuracy,
    grounding_proxy,
    has_safety_disclaimer,
    relevance_proxy,
)
from src.evaluation.retrieval_metrics import (
    mrr,
    precision_at_k,
    recall_at_k,
    relevant_keys,
    score_retrieval,
    work_key,
)


def _chunk(source):
    return {"metadata": {"source": source}}


# ── retrieval metrics ────────────────────────────────────────────────

def test_work_key_maps_gold_labels_to_canonical_titles():
    # Gold labels and chunk filenames must normalize to the same work key.
    assert work_key("charaka-chikitsa-ch29") == work_key("charaka_samhita_pv_sharma.pdf")
    assert work_key("afi-vol1") == work_key("afi_part1.pdf")
    assert work_key("api-vol1-monograph") == work_key("api_all_volume.pdf")


def test_work_key_afi_and_api_do_not_collide():
    assert work_key("afi-vol1") != work_key("api-vol1-monograph")


def test_recall_at_k_hits_when_relevant_in_window():
    retrieved = ["a", "b", "c", "d"]
    assert recall_at_k(retrieved, {"c"}, k=3) == 1.0   # c is in top-3
    assert recall_at_k(retrieved, {"d"}, k=3) == 0.0   # d is rank 4, outside top-3


def test_recall_at_k_no_relevant_is_zero():
    assert recall_at_k(["a", "b"], set(), k=2) == 0.0


def test_precision_at_k_counts_relevant_in_window():
    retrieved = ["a", "b", "a", "c"]
    # top-4 has 3 'a'/'c'-relevant of 4 -> 0.75
    assert precision_at_k(retrieved, {"a", "c"}, k=4) == 0.75


def test_precision_at_k_short_list_not_penalized():
    # Only 2 results but k=5 -> denominator is 2, not 5.
    assert precision_at_k(["a", "b"], {"a"}, k=5) == 0.5


def test_mrr_reports_first_relevant_rank():
    assert mrr(["a", "b", "c"], {"b"}) == 0.5      # rank 2 -> 1/2
    assert mrr(["a", "b", "c"], {"a"}) == 1.0      # rank 1
    assert mrr(["a", "b", "c"], {"z"}) == 0.0      # none


def test_score_retrieval_work_level_hit():
    # A Charaka chunk should count as relevant to the charaka gold source.
    retrieved = [_chunk("charaka_samhita_pv_sharma.pdf"),
                 _chunk("sushruta_samhita_vol_1.pdf")]
    scores = score_retrieval(retrieved, ["charaka-chikitsa-ch29"], k=6)
    assert scores["hit"] == 1.0
    assert scores["recall_at_k"] == 1.0
    assert scores["mrr"] == 1.0                     # charaka is rank 1


def test_score_retrieval_miss():
    retrieved = [_chunk("sushruta_samhita_vol_1.pdf")]
    scores = score_retrieval(retrieved, ["charaka-chikitsa-ch29"], k=6)
    assert scores["hit"] == 0.0
    assert scores["mrr"] == 0.0


def test_relevant_keys_dedupes():
    assert relevant_keys(["charaka-chikitsa-ch29", "charaka-sutra-ch1"]) == {
        work_key("charaka-chikitsa-ch29")
    }


# ── generation metrics ───────────────────────────────────────────────

def _sources(n):
    return [{"citation_number": i, "document": f"doc-{i}"} for i in range(1, n + 1)]


def test_citation_accuracy_all_valid():
    assert citation_accuracy("Claim【1】 and【2】.", _sources(2)) == 1.0


def test_citation_accuracy_partial():
    # One valid (1), one hallucinated (9) -> 1/2.
    assert citation_accuracy("Real【1】 fake【9】.", _sources(1)) == 0.5


def test_citation_accuracy_no_markers_is_vacuously_one():
    assert citation_accuracy("No citations here.", _sources(3)) == 1.0


def test_grounding_proxy_measures_overlap():
    answer = "Guggulu treats amavata"
    context = "Guggulu is indicated for amavata and vataroga"
    # 'guggulu', 'treats', 'amavata' -> 'treats' absent from context -> 2/3.
    assert round(grounding_proxy(answer, context), 3) == round(2 / 3, 3)


def test_grounding_proxy_empty_answer_is_zero():
    assert grounding_proxy("", "some context") == 0.0


def test_relevance_proxy_measures_question_overlap():
    question = "What treats amavata?"
    answer = "Guggulu treats amavata effectively"
    # content words of question: 'treats', 'amavata' (stopwords/short removed);
    # both appear in the answer -> 1.0
    assert relevance_proxy(answer, question) == 1.0


def test_has_safety_disclaimer():
    assert has_safety_disclaimer(
        "... under qualified practitioner (Vaidya) guidance."
    ) is True
    assert has_safety_disclaimer("No disclaimer present.") is False


# ── rerank-skip validity gate (run_eval with faked retrieval) ─────────

def _run_with_skips(monkeypatch, tmp_path, skipped_flags):
    import json
    from src.evaluation import run_eval as re_mod

    dataset = [{"id": f"q{i}", "question": f"question {i}", "gold_works": []}
               for i in range(len(skipped_flags))]
    path = tmp_path / "ds.json"
    path.write_text(json.dumps(dataset), encoding="utf-8")
    flags = iter(skipped_flags)
    monkeypatch.setattr(re_mod, "load_parent_store", lambda: None)
    monkeypatch.setattr(re_mod.embedder, "enable_embedding_cache", lambda *a: None)
    monkeypatch.setattr(re_mod.embedder, "save_embedding_cache", lambda: None)
    monkeypatch.setattr(re_mod, "_retrieve", lambda q, k, ps, **kw: {
        "scored": [], "context_block": "", "sources": [], "final_passages": [],
        "rerank_skipped": next(flags),
    })
    return re_mod.run_eval(path, tmp_path / "out", mode="retrieval", k=6)


def test_run_eval_valid_when_no_rerank_skips(monkeypatch, tmp_path):
    payload = _run_with_skips(monkeypatch, tmp_path, [False, False])
    assert payload["status"] == "VALID"
    assert payload["summary"]["rerank_skips"] == 0


def test_run_eval_invalid_when_any_rerank_skipped(monkeypatch, tmp_path):
    payload = _run_with_skips(monkeypatch, tmp_path, [False, True, True])
    assert payload["status"] == "INVALID"
    assert payload["summary"]["rerank_skips"] == 2
    assert [r["rerank_skipped"] for r in payload["results"]] == [False, True, True]


# ── pipeline selection in _retrieve (all stages faked) ────────────────

def _fake_stages(monkeypatch):
    from src.evaluation import run_eval as re_mod
    calls = []
    fused = [{"chunk_id": f"c{i}"} for i in range(20)]
    monkeypatch.setattr(re_mod, "semantic_search", lambda v, hyde_passages=None: [])
    monkeypatch.setattr(re_mod, "keyword_search", lambda v: [])
    monkeypatch.setattr(re_mod, "reciprocal_rank_fusion", lambda lists: list(fused))

    def fake_rerank(q, results):
        calls.append("rerank")
        return list(reversed(results))[:15], False

    def fake_mmr(q, results, top_k):
        calls.append("mmr")
        return results[1:top_k + 1]

    monkeypatch.setattr(re_mod, "rerank_with_retry", fake_rerank)
    monkeypatch.setattr(re_mod, "mmr_rerank", fake_mmr)
    return re_mod, calls


def test_retrieve_rrf_pipeline_skips_rerank_and_mmr(monkeypatch):
    re_mod, calls = _fake_stages(monkeypatch)
    out = re_mod._retrieve("q", 6, None, pipeline="rrf", need_context=False)
    assert calls == []
    assert [r["chunk_id"] for r in out["scored"]][:2] == ["c0", "c1"]
    assert len(out["scored"]) == 15


def test_retrieve_rerank_pipeline_retrieval_only_skips_mmr(monkeypatch):
    re_mod, calls = _fake_stages(monkeypatch)
    out = re_mod._retrieve("q", 6, None, pipeline="rerank", need_context=False)
    assert calls == ["rerank"]
    assert out["scored"][0]["chunk_id"] == "c19"


def test_retrieve_rerank_mmr_pipeline_scores_mmr_output(monkeypatch):
    re_mod, calls = _fake_stages(monkeypatch)
    out = re_mod._retrieve("q", 6, None, pipeline="rerank_mmr", need_context=False)
    assert calls == ["rerank", "mmr"]
    assert [r["chunk_id"] for r in out["scored"]] == ["c18", "c17", "c16", "c15", "c14", "c13"]
