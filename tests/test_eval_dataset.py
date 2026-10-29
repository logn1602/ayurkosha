"""Checks data/eval/eval_dataset.json against eval_dataset.schema.json.

A lightweight check of required fields, enums and types (no jsonschema dependency),
plus: every gold label resolves to a canonical work.

Run: python -m pytest tests/test_eval_dataset.py
"""

import json
from pathlib import Path

from src.evaluation.retrieval_metrics import _CANONICAL_BY_LOWER, work_key

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
        allowed = ITEM["properties"]["gold_sources"]["items"]["enum"]
        assert item["gold_sources"] and set(item["gold_sources"]) <= set(allowed), item["id"]
        assert len(item["gold_sources"]) == len(set(item["gold_sources"])), item["id"]


def test_provenance_records():
    for item in DATASET:
        prov = item["provenance"]
        assert set(prov) == set(PROV["required"]), item["id"]
        assert prov["method"] in PROV["properties"]["method"]["enum"]
        assert isinstance(prov["supporting_chunk_ids"], list)
        if prov["method"] == "corpus-evidence-v1":    # criteria-based labels must cite evidence
            assert prov["criteria_version"] and prov["supporting_chunk_ids"], item["id"]


def test_gold_labels_resolve_to_canonical_works():
    canonical = set(_CANONICAL_BY_LOWER.values())
    for item in DATASET:
        for label in item["gold_sources"]:
            assert work_key(label) in canonical, (item["id"], label)
