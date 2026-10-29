"""Tests for src/query/hyde.py and HyDE support in semantic_search.

The Claude client, Cohere embedder, and Pinecone query are all faked — no
live API calls.

Run: python -m pytest tests/test_hyde.py
"""

from types import SimpleNamespace

from src.query import hyde
from src.retrieval import semantic


class _FakeClient:
    def __init__(self, text=None, exc=None):
        self.text, self.exc = text, exc
        self.calls = []
        self.messages = self

    def create(self, **kwargs):
        self.calls.append(kwargs)
        if self.exc:
            raise self.exc
        return SimpleNamespace(content=[SimpleNamespace(type="text", text=self.text)])


# ── generate_hypothetical_document ────────────────────────────────────

def test_hyde_returns_stripped_passage(monkeypatch):
    client = _FakeClient(text="  Amavata is treated with Simhanada Guggulu.  ")
    monkeypatch.setattr(hyde, "_get_client", lambda: client)
    out = hyde.generate_hypothetical_document("joint pain and swelling")
    assert out == "Amavata is treated with Simhanada Guggulu."
    assert "joint pain and swelling" in client.calls[0]["messages"][0]["content"]


def test_hyde_fails_safe_on_api_error(monkeypatch):
    client = _FakeClient(exc=RuntimeError("credit balance too low"))
    monkeypatch.setattr(hyde, "_get_client", lambda: client)
    assert hyde.generate_hypothetical_document("joint pain") is None


def test_hyde_empty_response_returns_none(monkeypatch):
    monkeypatch.setattr(hyde, "_get_client", lambda: _FakeClient(text="   "))
    assert hyde.generate_hypothetical_document("joint pain") is None


def test_hyde_empty_query_skips_api(monkeypatch):
    client = _FakeClient(text="unused")
    monkeypatch.setattr(hyde, "_get_client", lambda: client)
    assert hyde.generate_hypothetical_document("   ") is None
    assert client.calls == []


# ── semantic_search with hyde_passages ────────────────────────────────

def _patch_retrieval(monkeypatch, hits_by_vec):
    embedded = {"query": [], "document": []}

    def fake_embed_query(text):
        embedded["query"].append(text)
        return ("q", text)

    def fake_embed_documents(texts):
        embedded["document"].extend(texts)
        return [("d", t) for t in texts]

    def fake_query(vec, top_k, doc_type_filter, index):
        return [dict(chunk_id=cid, score=score) for cid, score in hits_by_vec.get(vec, [])]

    monkeypatch.setattr(semantic, "embed_query", fake_embed_query)
    monkeypatch.setattr(semantic, "embed_documents", fake_embed_documents)
    monkeypatch.setattr(semantic.pinecone_store, "query", fake_query)
    return embedded


def test_semantic_search_embeds_hyde_as_documents_and_merges(monkeypatch):
    embedded = _patch_retrieval(monkeypatch, {
        ("q", "joint pain"): [("c1", 0.5), ("c2", 0.4)],
        ("d", "Amavata passage"): [("c2", 0.9), ("c3", 0.7)],
    })
    results = semantic.semantic_search(
        "joint pain", top_n=5, index=object(), hyde_passages=["Amavata passage"]
    )
    assert embedded == {"query": ["joint pain"], "document": ["Amavata passage"]}
    assert [r["chunk_id"] for r in results] == ["c2", "c3", "c1"]
    assert results[0]["score"] == 0.9          # best score kept on dedupe
    assert [r["rank"] for r in results] == [0, 1, 2]


def test_semantic_search_without_hyde_skips_document_embedding(monkeypatch):
    embedded = _patch_retrieval(monkeypatch, {("q", "joint pain"): [("c1", 0.5)]})
    results = semantic.semantic_search("joint pain", top_n=5, index=object(),
                                       hyde_passages=["", "  "])
    assert embedded["document"] == []
    assert [r["chunk_id"] for r in results] == ["c1"]
