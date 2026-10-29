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


# ── disk embedding cache ──────────────────────────────────────────────

def _fake_embed(monkeypatch):
    from src.ingestion import embedder
    calls = []

    def fake(texts, input_type):
        calls.append((input_type, list(texts)))
        return [[float(len(t)), 1.0 if input_type == "search_query" else 0.0] for t in texts]

    monkeypatch.setattr(embedder, "_embed_with_retry", fake)
    return embedder, calls


def test_embedding_cache_serves_hits_and_persists(monkeypatch, tmp_path):
    embedder, calls = _fake_embed(monkeypatch)
    path = tmp_path / "cache.json"
    embedder.enable_embedding_cache(path)
    try:
        first = embedder.embed_query("joint pain")
        again = embedder.embed_query("joint pain")
        docs = embedder.embed_documents(["joint pain", "fever"])
        assert first == again
        assert docs[0] != first                 # input_type is part of the key
        assert calls == [("search_query", ["joint pain"]),
                         ("search_document", ["joint pain", "fever"])]
        embedder.save_embedding_cache()
    finally:
        embedder.disable_embedding_cache()

    embedder.enable_embedding_cache(path)       # fresh process: load from disk
    try:
        assert embedder.embed_documents(["fever", "cough"])[0] == docs[1]
        assert calls[-1] == ("search_document", ["cough"])   # only the miss
    finally:
        embedder.disable_embedding_cache()


def test_embedding_cache_disabled_by_default(monkeypatch):
    embedder, calls = _fake_embed(monkeypatch)
    embedder.embed_query("joint pain")
    embedder.embed_query("joint pain")
    assert len(calls) == 2
