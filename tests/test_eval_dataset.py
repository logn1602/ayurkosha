"""Checks data/eval/eval_dataset.json against eval_dataset.schema.json.

A lightweight check of required fields, enums and types (no jsonschema dependency),
plus: every gold label resolves to a canonical work.

Run: python -m pytest tests/test_eval_dataset.py
"""

import json
from pathlib import Path

from src.evaluation.retrieval_metrics import _CANONICAL_BY_LOWER, parse_support_id, work_key

EVAL_DIR = Path(__file__).resolve().parents[1] / "data" / "eval"
DATASET = json.loads((EVAL_DIR / "eval_dataset.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((EVAL_DIR / "eval_dataset.schema.json").read_text(encoding="utf-8"))
ITEM = SCHEMA["items"]
PROV = ITEM["properties"]["provenance"]


def test_items_have_exactly_the_schema_fields():
    for item in DATASET:
        assert set(ITEM["required"]) <= set(item), item["id"]
        assert set(item) <= set(ITEM["properties"]), item["id"]


def test_enums_and_unique_ids():
    ids = [item["id"] for item in DATASET]
    assert len(ids) == len(set(ids))
    for item in DATASET:
        assert item["category"] in ITEM["properties"]["category"]["enum"]
        assert item["difficulty"] in ITEM["properties"]["difficulty"]["enum"]
        allowed = ITEM["properties"]["gold_works"]["items"]["enum"]
        assert item["gold_works"] and set(item["gold_works"]) <= set(allowed), item["id"]
        assert len(item["gold_works"]) == len(set(item["gold_works"])), item["id"]


def test_provenance_records():
    for item in DATASET:
        prov = item["provenance"]
        assert set(prov) == set(PROV["required"]), item["id"]
        assert prov["method"] in PROV["properties"]["method"]["enum"]
        assert isinstance(prov["supporting_chunk_ids"], list)
        if prov["method"] != "bm25-keyword-evidence":   # criteria-based labels must cite evidence
            assert prov["criteria_version"] and prov["supporting_chunk_ids"], item["id"]


def test_reviewer_recorded_only_after_confirmation():
    """Pending labels name no reviewer; confirmed ones must name who confirmed them."""
    for item in DATASET:
        prov = item["provenance"]
        if prov["method"].endswith(": pending"):
            assert prov["reviewed_by"] is None, item["id"]
        elif prov["method"] == "agent-proposed from corpus text, human-reviewed":
            assert prov["reviewed_by"], item["id"]


def test_gold_passages_are_evidenced_parents_of_gold_works():
    for item in DATASET:
        assert item["gold_passages"], item["id"]
        assert set(item["gold_passages"]) <= set(item["provenance"]["supporting_chunk_ids"]), item["id"]
        works = {work_key(w) for w in item["gold_works"]}
        for pid in item["gold_passages"]:
            parsed = parse_support_id(pid)
            assert parsed and work_key(parsed[0]) in works, (item["id"], pid)


def test_formulary_sets_are_passage_gold_only_where_formulations_are_asked_for():
    """eval_017 asks for formulations; 018-023/025 ask for a line of treatment or an
    approach, so their AFI monograph sets stay work-level evidence (LABELING_CRITERIA.md)."""
    rows = {item["id"]: item for item in DATASET}
    assert all(p.startswith("afi") for p in rows["eval_017"]["gold_passages"])
    for qid in ("eval_018", "eval_019", "eval_020", "eval_021", "eval_022", "eval_023", "eval_025"):
        assert "afi" in rows[qid]["gold_works"], qid
        assert not any(p.startswith("afi") for p in rows[qid]["gold_passages"]), qid
        assert any(c.startswith("afi") for c in rows[qid]["provenance"]["supporting_chunk_ids"]), qid


def _chunk_on(parent_id, text_name):
    stem, page = parse_support_id(parent_id)
    return {"chunk_id": f"{parent_id}_C0", "parent_id": parent_id,
            "metadata": {"source": stem[: -len("_pdf")] + ".pdf", "page": page, "text_name": text_name}}


def test_eval_018_passage_scoring_ignores_formulary_chunks_but_work_level_counts_them():
    from src.evaluation import traces
    from src.evaluation.retrieval_metrics import score_passages, score_retrieval

    path = EVAL_DIR / "eval_dataset.json"
    works, passages = traces.load_labels(path)["eval_018"], traces.load_gold_passages(path)["eval_018"]
    item = next(i for i in DATASET if i["id"] == "eval_018")
    afi_evidence = next(c for c in item["provenance"]["supporting_chunk_ids"] if c.startswith("afi"))
    formulary = [_chunk_on(afi_evidence, "Ayurvedic Formulary of India")]   # a monograph in the Jvara set

    assert score_retrieval(formulary, works, k=6)["hit"] == 1.0             # work level: the Formulary is gold
    assert score_passages(formulary, passages, k=6)["hit"] == 0.0           # passage level: not a strict answer
    sushruta = _chunk_on(passages[0], "Sushruta Samhita")
    scores = score_passages(formulary + [sushruta], passages, k=6)
    assert scores["hit"] == 1.0 and scores["mrr_at_k"] == 0.5               # the Sushruta chunk, at rank 2


def test_gold_labels_resolve_to_canonical_works():
    canonical = set(_CANONICAL_BY_LOWER.values())
    for item in DATASET:
        for label in item["gold_works"]:
            assert work_key(label) in canonical, (item["id"], label)


def test_questions_are_plain_ascii():
    """The 'before' run tokenizes queries the old way, which splits words at
    diacritics ("Āmavāta" -> "mav", "ta"), so questions must be plain ASCII."""
    offenders = [item["id"] for item in DATASET if not item["question"].isascii()]
    assert not offenders, offenders
