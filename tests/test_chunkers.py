"""Tests for src/ingestion/chunkers.py.

Run: python -m pytest tests/test_chunkers.py
"""

from src.ingestion.chunkers import (
    split_text,
    chunk_record,
    chunk_records,
    CHILD_CHUNK_SIZE,
    PARENT_CHUNK_SIZE,
)


# ── split_text ────────────────────────────────────────────────────────

def test_split_short_text_single_chunk():
    assert split_text("short text", 100) == ["short text"]


def test_split_respects_size():
    text = ". ".join(f"sentence number {i} with some filler words" for i in range(200))
    chunks = split_text(text, 300, 0)
    assert len(chunks) > 1
    assert all(len(c) <= 300 for c in chunks)


def test_split_overlap_carries_context():
    text = " ".join(f"word{i}" for i in range(200))
    chunks = split_text(text, 120, 40)
    assert len(chunks) > 1
    # Consecutive chunks should share some trailing/leading content.
    assert any(
        set(a.split()) & set(b.split())
        for a, b in zip(chunks, chunks[1:])
    )


def test_split_hard_splits_unbreakable_unit():
    text = "x" * 1000  # no separators at all
    chunks = split_text(text, 100, 0)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == text


def test_split_empty():
    assert split_text("", 100) == []
    assert split_text("   ", 100) == []


# ── chunk_record parent/child structure ───────────────────────────────

def test_chunk_record_produces_parents_and_children():
    text = ("Ashwagandha is a Rasayana herb. " * 300)
    rec = {"text": text,
           "metadata": {"source": "note.pdf", "doc_type": "clinical", "page": 5}}
    out = chunk_record(rec)
    assert out["parents"] and out["children"]
    # More children than parents (children are smaller).
    assert len(out["children"]) >= len(out["parents"])


def test_chunk_ids_unique_and_linked():
    text = "Guduchi immunomodulator. " * 300
    rec = {"text": text,
           "metadata": {"source": "a.pdf", "doc_type": "clinical", "page": 1}}
    out = chunk_record(rec)
    parent_ids = {p["chunk_id"] for p in out["parents"]}
    child_ids = [c["chunk_id"] for c in out["children"]]
    # ids unique
    assert len(child_ids) == len(set(child_ids))
    # every child references an existing parent
    for c in out["children"]:
        assert c["parent_id"] in parent_ids
        assert c["metadata"]["parent_id"] in parent_ids
        assert c["metadata"]["is_parent"] is False


def test_chunk_sizes_bounded():
    text = "Haridra anti-inflammatory turmeric compound. " * 300
    rec = {"text": text,
           "metadata": {"source": "b.pdf", "doc_type": "clinical", "page": 2}}
    out = chunk_record(rec)
    assert all(len(p["text"]) <= PARENT_CHUNK_SIZE for p in out["parents"])
    assert all(len(c["text"]) <= CHILD_CHUNK_SIZE for c in out["children"])


def test_metadata_propagated_to_chunks():
    rec = {"text": "Charaka Samhita passage. " * 100,
           "metadata": {"source": "charaka.pdf", "doc_type": "classical_text",
                        "page": 415, "text_name": "Charaka Samhita",
                        "sthana": "Chikitsasthana"}}
    out = chunk_record(rec)
    for c in out["children"]:
        assert c["metadata"]["text_name"] == "Charaka Samhita"
        assert c["metadata"]["sthana"] == "Chikitsasthana"
        assert c["metadata"]["doc_type"] == "classical_text"


def test_empty_record():
    rec = {"text": "   ", "metadata": {"source": "x.pdf", "page": 1}}
    out = chunk_record(rec)
    assert out == {"parents": [], "children": []}


# ── chunk_records aggregation ─────────────────────────────────────────

def test_chunk_records_unique_ids_across_corpus():
    recs = [
        {"text": "Passage one about Amalaki. " * 100,
         "metadata": {"source": "doc1.pdf", "doc_type": "clinical", "page": 1}},
        {"text": "Passage two about Guduchi. " * 100,
         "metadata": {"source": "doc2.pdf", "doc_type": "clinical", "page": 1}},
    ]
    out = chunk_records(recs)
    all_ids = [c["chunk_id"] for c in out["children"]] + \
              [p["chunk_id"] for p in out["parents"]]
    assert len(all_ids) == len(set(all_ids))  # globally unique
