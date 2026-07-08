"""Tests for src/ingestion/bm25_store.py and parent_store.py.

Run: python -m pytest tests/test_stores.py
"""

import pytest

from src.ingestion.bm25_store import (
    build_bm25_index,
    save_bm25_index,
    load_bm25_index,
)
from src.ingestion.parent_store import (
    build_parent_store,
    save_parent_store,
    load_parent_store,
)


def _sample_children():
    return [
        {"chunk_id": "d_1_P0_C0", "parent_id": "d_1_P0",
         "text": "Amalaki is a rich source of vitamin C and a Rasayana.",
         "metadata": {"source": "d.pdf", "doc_type": "pharmacopoeia"}},
        {"chunk_id": "d_1_P0_C1", "parent_id": "d_1_P0",
         "text": "Guduchi (Tinospora cordifolia) is an immunomodulator.",
         "metadata": {"source": "d.pdf", "doc_type": "pharmacopoeia"}},
        {"chunk_id": "d_2_P0_C0", "parent_id": "d_2_P0",
         "text": "Haridra contains curcumin, an anti-inflammatory compound.",
         "metadata": {"source": "d.pdf", "doc_type": "pharmacopoeia"}},
    ]


def _sample_parents():
    return [
        {"chunk_id": "d_1_P0",
         "text": "Amalaki is a rich source of vitamin C and a Rasayana. "
                 "Guduchi is an immunomodulator.",
         "metadata": {"source": "d.pdf", "is_parent": True}},
        {"chunk_id": "d_2_P0",
         "text": "Haridra contains curcumin, an anti-inflammatory compound.",
         "metadata": {"source": "d.pdf", "is_parent": True}},
    ]


# ── BM25 store ────────────────────────────────────────────────────────

def test_bm25_build_and_search():
    index = build_bm25_index(_sample_children())
    assert len(index) == 3
    hits = index.search("Guduchi immunomodulator", top_n=3)
    assert hits, "expected at least one hit"
    assert hits[0]["chunk_id"] == "d_1_P0_C1"
    assert hits[0]["score"] > 0


def test_bm25_synonym_match():
    # Query "Amla" should hit the chunk that only says "Amalaki" (synonym
    # expansion happens inside the tokenizer on both sides).
    index = build_bm25_index(_sample_children())
    hits = index.search("Amla vitamin C", top_n=3)
    assert hits
    assert hits[0]["chunk_id"] == "d_1_P0_C0"


def test_bm25_empty_query_returns_nothing():
    index = build_bm25_index(_sample_children())
    assert index.search("   ", top_n=5) == []


def test_bm25_save_and_load_roundtrip(tmp_path):
    index = build_bm25_index(_sample_children())
    path = tmp_path / "bm25.pkl"
    save_bm25_index(index, path)
    loaded = load_bm25_index(path)
    assert len(loaded) == 3
    hits = loaded.search("curcumin anti-inflammatory", top_n=3)
    assert hits[0]["chunk_id"] == "d_2_P0_C0"


def test_bm25_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bm25_index(tmp_path / "nope.pkl")


def test_bm25_no_chunks_raises():
    with pytest.raises(ValueError):
        build_bm25_index([{"chunk_id": "x", "text": "   ", "metadata": {}}])


# ── Parent store ──────────────────────────────────────────────────────

def test_parent_store_lookup():
    store = build_parent_store(_sample_parents())
    assert len(store) == 2
    assert "d_1_P0" in store
    assert store.get_parent_text("d_1_P0").startswith("Amalaki")
    assert store.get_parent("missing") is None


def test_parent_store_expand_dedupes():
    store = build_parent_store(_sample_parents())
    children = _sample_children()  # first two share parent d_1_P0
    expanded = store.expand(children)
    ids = [p["chunk_id"] for p in expanded]
    assert ids == ["d_1_P0", "d_2_P0"]  # deduped, order preserved


def test_parent_store_expand_fallback_to_child():
    store = build_parent_store(_sample_parents())
    orphan = {"chunk_id": "orphan_C0", "parent_id": "unknown_P9",
              "text": "orphaned chunk", "metadata": {}}
    expanded = store.expand([orphan])
    assert expanded[0]["chunk_id"] == "orphan_C0"


def test_parent_store_save_load_roundtrip(tmp_path):
    store = build_parent_store(_sample_parents())
    path = tmp_path / "parents.json"
    save_parent_store(store, path)
    loaded = load_parent_store(path)
    assert len(loaded) == 2
    assert loaded.get_parent_text("d_2_P0").startswith("Haridra")


def test_parent_store_load_missing_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_parent_store(tmp_path / "nope.json")
