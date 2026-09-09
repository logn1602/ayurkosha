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
