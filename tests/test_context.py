"""Tests for src/context/{builder,reorder,parent_expand}.py (pure logic — no API).

Run: python -m pytest tests/test_context.py
"""

from src.context.builder import build_context
from src.context.parent_expand import expand_to_parents
from src.context.reorder import reorder_chunks
from src.ingestion.parent_store import ParentStore


def _mk(chunk_id, source, page, text="text", **extra):
    chunk = {"chunk_id": chunk_id, "text": text,
              "metadata": {"source": source, "page": page}}
    chunk.update(extra)
    return chunk


# ── reorder_chunks ──────────────────────────────────────────

def test_reorder_sorts_by_source_then_page():
    chunks = [
        _mk("b_2_P0", "b", 2),
        _mk("a_1_P0", "a", 1),
        _mk("a_2_P0", "a", 2),
    ]
    ordered = reorder_chunks(chunks)
    assert [c["chunk_id"] for c in ordered] == ["a_1_P0", "a_2_P0", "b_2_P0"]


def test_reorder_uses_chunk_index_within_same_page():
    chunks = [
        _mk("doc_1_P2", "doc", 1),
        _mk("doc_1_P0", "doc", 1),
        _mk("doc_1_P1", "doc", 1),
    ]
    ordered = reorder_chunks(chunks)
    assert [c["chunk_id"] for c in ordered] == ["doc_1_P0", "doc_1_P1", "doc_1_P2"]


def test_reorder_handles_missing_page():
    chunks = [_mk("doc_None_P0", "doc", None), _mk("doc_1_P0", "doc", 1)]
    ordered = reorder_chunks(chunks)
    assert [c["metadata"]["page"] for c in ordered] == [None, 1]


# ── build_context ───────────────────────────────────────────

def test_build_context_numbers_sources_in_order():
    chunks = [
        {"text": "first passage", "metadata": {"source": "a.pdf", "page": 1}},
        {"text": "second passage", "metadata": {"source": "b.pdf", "page": 2,
                                                 "citation": "B Samhita, p. 2"}},
    ]
    context, sources = build_context(chunks)
    assert "【Source 1】" in context and "【Source 2】" in context
    assert "first passage" in context and "second passage" in context
    assert sources[0]["citation_number"] == 1 and sources[0]["document"] == "a.pdf"
    assert sources[1]["document"] == "B Samhita, p. 2"  # prefers citation over source


def test_build_context_section_prefers_heading_path():
    chunks = [{"text": "t", "metadata": {"source": "a", "page": 1,
                                          "heading_path": ["DOSE", "CAUTION"],
                                          "sthana": "Chikitsasthana"}}]
    context, _ = build_context(chunks)
    assert "DOSE > CAUTION" in context


def test_build_context_empty():
    context, sources = build_context([])
    assert context == "" and sources == []


# ── expand_to_parents ────────────────────────────────────────

def test_expand_to_parents_replaces_text_and_keeps_retrieval_text():
    store = ParentStore({"P0": {"chunk_id": "P0", "text": "full parent text",
                                 "metadata": {"source": "a", "page": 1}}})
    child = {"chunk_id": "P0_C0", "parent_id": "P0", "text": "child snippet",
             "rank": 0, "score": 0.9, "metadata": {"parent_id": "P0"}}
    expanded = expand_to_parents([child], store)
    assert len(expanded) == 1
    assert expanded[0]["text"] == "full parent text"
    assert expanded[0]["retrieval_text"] == "child snippet"
    assert expanded[0]["score"] == 0.9  # retrieval fields preserved


def test_expand_to_parents_dedupes_by_parent():
    store = ParentStore({"P0": {"chunk_id": "P0", "text": "parent", "metadata": {}}})
    children = [
        {"chunk_id": "P0_C0", "parent_id": "P0", "text": "c0"},
        {"chunk_id": "P0_C1", "parent_id": "P0", "text": "c1"},
    ]
    expanded = expand_to_parents(children, store)
    assert len(expanded) == 1


def test_expand_to_parents_falls_back_when_parent_missing():
    store = ParentStore({})
    child = {"chunk_id": "P0_C0", "parent_id": "P0", "text": "child only"}
    expanded = expand_to_parents([child], store)
    assert len(expanded) == 1
    assert expanded[0]["text"] == "child only"
    assert expanded[0]["retrieval_text"] == "child only"
