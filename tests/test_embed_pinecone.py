"""Unit tests for embedder.py and pinecone_store.py that do NOT hit live APIs.

Only pure helpers (batching, metadata sanitization, vector building) are
covered here; end-to-end embedding/upsert is exercised by the pipeline smoke
test against the real services.

Run: python -m pytest tests/test_embed_pinecone.py
"""

import pytest

from src.ingestion.embedder import _batched, MAX_BATCH, embed_query
from src.ingestion.pinecone_store import _sanitize_metadata, _to_vector, MAX_METADATA_TEXT


# ── embedder helpers ──────────────────────────────────────────────────

def test_batched_groups():
    items = list(range(200))
    batches = list(_batched(items, MAX_BATCH))
    assert len(batches) == 3            # 96 + 96 + 8
    assert [len(b) for b in batches] == [96, 96, 8]
    assert sum(len(b) for b in batches) == 200


def test_batched_exact_multiple():
    batches = list(_batched(list(range(192)), MAX_BATCH))
    assert [len(b) for b in batches] == [96, 96]


def test_embed_query_rejects_empty():
    with pytest.raises(ValueError):
        embed_query("   ")


# ── pinecone metadata sanitization ────────────────────────────────────

def test_sanitize_drops_none():
    out = _sanitize_metadata({"a": None, "b": "x"})
    assert "a" not in out
    assert out["b"] == "x"


def test_sanitize_preserves_scalars_and_bool():
    out = _sanitize_metadata({"page": 12, "score": 1.5, "is_monograph": True, "s": "t"})
    assert out["page"] == 12
    assert out["score"] == 1.5
    assert out["is_monograph"] is True
    assert out["s"] == "t"


def test_sanitize_coerces_list_to_str_and_drops_none_elements():
    out = _sanitize_metadata({"headings": ["A", None, 3]})
    assert out["headings"] == ["A", "3"]


def test_sanitize_stringifies_unknown_types():
    out = _sanitize_metadata({"obj": {"nested": 1}})
    assert isinstance(out["obj"], str)


# ── vector building ───────────────────────────────────────────────────

def test_to_vector_shape_and_text_in_metadata():
    chunk = {
        "chunk_id": "d_1_P0_C0",
        "parent_id": "d_1_P0",
        "text": "Amalaki is a Rasayana.",
        "embedding": [0.1] * 8,
        "metadata": {"source": "d.pdf", "doc_type": "pharmacopoeia", "page": 3},
    }
    vec = _to_vector(chunk)
    assert vec["id"] == "d_1_P0_C0"
    assert vec["values"] == [0.1] * 8
    assert vec["metadata"]["text"] == "Amalaki is a Rasayana."
    assert vec["metadata"]["parent_id"] == "d_1_P0"
    assert vec["metadata"]["doc_type"] == "pharmacopoeia"


def test_to_vector_truncates_long_text():
    long_text = "x" * (MAX_METADATA_TEXT + 500)
    chunk = {"chunk_id": "c1", "text": long_text, "embedding": [0.0],
             "metadata": {}}
    vec = _to_vector(chunk)
    assert len(vec["metadata"]["text"]) == MAX_METADATA_TEXT
