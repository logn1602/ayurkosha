"""
AyurKosha — Shared API Dependencies
Provides process-lifetime singletons that aren't already self-initializing.

Pinecone (src/ingestion/pinecone_store.py), BM25
(src/retrieval/keyword.py), Cohere (src/reranking/cohere_rerank.py), and
Anthropic (src/generation/generator.py, src/query/expander.py) clients all
lazily construct and cache themselves on first use inside their own modules —
there's nothing for this module to wrap there. The one dependency that
doesn't already have a module-level cache is the ParentStore (it's loaded
per-call by src/context/parent_expand.py's default), so a request-scoped
FastAPI dependency here avoids re-reading parent_store.json from disk on
every /query call.

Build this in: Phase 5
"""

from __future__ import annotations

from src.ingestion.parent_store import ParentStore, load_parent_store

_parent_store: ParentStore | None = None


def get_parent_store() -> ParentStore:
    """FastAPI dependency: lazily load and cache the ParentStore for the process."""
    global _parent_store
    if _parent_store is None:
        _parent_store = load_parent_store()
    return _parent_store
