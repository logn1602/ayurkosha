"""
AyurKosha — Pinecone Storage
Creates the serverless index and upserts child-chunk vectors + metadata.

Config (from settings / project doc §8.2):
  - dimension : 1024 (Cohere embed-multilingual-v3.0)
  - metric    : cosine
  - spec      : ServerlessSpec(cloud="aws", region="us-east-1")

Only CHILD chunks are stored here (they are what we retrieve on); parent
context lives in parent_store.py. Each vector carries source-traceable
metadata (text, source, page, doc_type, chunk_id, citation, ...). Pinecone
metadata only allows str / number / bool / list[str], so values are sanitized
before upsert (None dropped, others coerced).

Build this in: Phase 2, Step 6
"""

from __future__ import annotations

import logging
import time
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

UPSERT_BATCH = 100          # Pinecone recommended batch size
CLOUD = "aws"
REGION = "us-east-1"
# Cap metadata text so a vector stays well under Pinecone's 40KB metadata limit.
MAX_METADATA_TEXT = 4000
# Retry transient network errors (DNS/connection blips) on Pinecone calls.
NET_RETRIES = 5
NET_BACKOFF = 3.0  # seconds; doubles each retry

_client = None


def _with_retry(fn, *args, what: str = "pinecone call", **kwargs):
    """Call a Pinecone operation, retrying transient network failures.

    A single DNS/connection blip should not abort a long ingest, so upserts and
    fetches are wrapped in exponential-backoff retries.
    """
    last_exc: Exception | None = None
    for attempt in range(NET_RETRIES):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:  # noqa: BLE001 — urllib3/pinecone raise varied types
            last_exc = exc
            wait = NET_BACKOFF * (2 ** attempt)
            logger.warning("%s failed (attempt %d/%d): %s — retrying in %.0fs",
                           what, attempt + 1, NET_RETRIES, exc, wait)
            time.sleep(wait)
    raise RuntimeError(f"{what} failed after {NET_RETRIES} attempts: {last_exc}")


def _get_client():
    """Lazily construct and cache the Pinecone client."""
    global _client
    if _client is not None:
        return _client
    from pinecone import Pinecone

    if not settings.pinecone_api_key:
        raise RuntimeError(
            "PINECONE_API_KEY is not set. Add it to .env before indexing."
        )
    _client = Pinecone(api_key=settings.pinecone_api_key)
    return _client


def _index_names(pc) -> list[str]:
    """Return existing index names, tolerating SDK response-shape differences."""
    listing = pc.list_indexes()
    if hasattr(listing, "names"):
        return list(listing.names())
    return [getattr(i, "name", i.get("name") if isinstance(i, dict) else i)
            for i in listing]


def ensure_index(name: str | None = None, wait: bool = True):
    """Create the serverless index if it doesn't exist; return the index handle.

    Idempotent: safe to call on every startup / ingest.
    """
    from pinecone import ServerlessSpec

    pc = _get_client()
    name = name or settings.pinecone_index_name

    if name not in _index_names(pc):
        logger.info("Creating Pinecone index '%s' (dim=%d, cosine, %s/%s).",
                    name, settings.embedding_dimensions, CLOUD, REGION)
        pc.create_index(
            name=name,
            dimension=settings.embedding_dimensions,
            metric="cosine",
            spec=ServerlessSpec(cloud=CLOUD, region=REGION),
        )
        if wait:
            while not pc.describe_index(name).status.get("ready", False):
                logger.info("Waiting for index '%s' to be ready...", name)
                time.sleep(2)
    else:
        logger.info("Pinecone index '%s' already exists.", name)

    return pc.Index(name)


def _sanitize_metadata(meta: dict[str, Any]) -> dict[str, Any]:
    """Coerce metadata to Pinecone-allowed types (str/number/bool/list[str]).

    - None values are dropped.
    - Lists are coerced to list[str] (None elements removed).
    - Other non-scalar values are stringified.
    """
    clean: dict[str, Any] = {}
    for key, value in meta.items():
        if value is None:
            continue
        if isinstance(value, bool) or isinstance(value, (int, float, str)):
            clean[key] = value
        elif isinstance(value, (list, tuple)):
            clean[key] = [str(v) for v in value if v is not None]
        else:
            clean[key] = str(value)
    return clean


def _to_vector(chunk: dict[str, Any]) -> dict[str, Any]:
    """Build a Pinecone vector record from an embedded chunk."""
    meta = dict(chunk.get("metadata", {}))
    # Ensure the text and key linkage fields are present in metadata so
    # retrieval can return them directly.
    text = chunk.get("text", "")
    meta.setdefault("text", text[:MAX_METADATA_TEXT])
    if chunk.get("parent_id"):
        meta.setdefault("parent_id", chunk["parent_id"])
    return {
        "id": chunk["chunk_id"],
        "values": chunk["embedding"],
        "metadata": _sanitize_metadata(meta),
    }


def _batched(items: list[Any], size: int):
    for i in range(0, len(items), size):
        yield items[i:i + size]


def upsert_chunks(chunks: list[dict[str, Any]], index=None) -> int:
    """Upsert embedded child chunks to Pinecone in batches of 100.

    Args:
        chunks: Child chunks that already have ``chunk_id``, ``embedding``, and
            ``metadata``.
        index: Optional index handle; created/fetched via ensure_index() if omitted.

    Returns:
        Number of vectors upserted.
    """
    if not chunks:
        return 0
    index = index or ensure_index()

    vectors = [_to_vector(c) for c in chunks if c.get("embedding")]
    total_batches = (len(vectors) + UPSERT_BATCH - 1) // UPSERT_BATCH
    for bi, batch in enumerate(_batched(vectors, UPSERT_BATCH), start=1):
        logger.info("Upserting to Pinecone: batch %d/%d (%d vectors).",
                    bi, total_batches, len(batch))
        _with_retry(index.upsert, vectors=batch, what="upsert")
    logger.info("Upserted %d vectors to index '%s'.",
                len(vectors), settings.pinecone_index_name)
    return len(vectors)


def fetch_existing_ids(ids: list[str], index=None) -> set[str]:
    """Return the subset of `ids` already present in the index.

    Used for resumable ingestion: chunks already upserted are skipped so a
    re-run after an interruption does not re-embed (and re-spend tokens on)
    work already done.
    """
    if not ids:
        return set()
    index = index or ensure_index()
    resp = _with_retry(index.fetch, ids=list(ids), what="fetch")
    vectors = resp.get("vectors", {}) if isinstance(resp, dict) else getattr(resp, "vectors", {})
    return set(vectors.keys())


def query(
    vector: list[float],
    top_k: int = None,
    doc_type_filter: str | None = None,
    index=None,
) -> list[dict[str, Any]]:
    """Query the index by embedding vector.

    Args:
        vector: Query embedding (from embedder.embed_query).
        top_k: Number of matches (defaults to settings.semantic_retrieve_n).
        doc_type_filter: Restrict to a single doc_type if given.
        index: Optional index handle.

    Returns:
        List of {chunk_id, score, text, parent_id, metadata} dicts.
    """
    index = index or ensure_index()
    top_k = top_k or settings.semantic_retrieve_n
    flt = {"doc_type": {"$eq": doc_type_filter}} if doc_type_filter else None

    resp = index.query(
        vector=vector,
        top_k=top_k,
        include_metadata=True,
        filter=flt,
    )
    matches = resp.get("matches", []) if isinstance(resp, dict) else resp.matches
    results: list[dict[str, Any]] = []
    for m in matches:
        md = m["metadata"] if isinstance(m, dict) else m.metadata
        mid = m["id"] if isinstance(m, dict) else m.id
        score = m["score"] if isinstance(m, dict) else m.score
        results.append({
            "chunk_id": mid,
            "score": float(score),
            "text": (md or {}).get("text", ""),
            "parent_id": (md or {}).get("parent_id"),
            "metadata": md or {},
        })
    return results


def delete_by_source(source: str, index=None) -> None:
    """Delete all vectors originating from a given source file name."""
    index = index or ensure_index()
    index.delete(filter={"source": {"$eq": source}})
    logger.info("Deleted vectors with source='%s'.", source)
