"""
AyurKosha — Embedding Module
Embeds text using Cohere's multilingual model with *asymmetric* input types.

Asymmetry is a free accuracy boost: documents are embedded with
``input_type="search_document"`` and queries with ``input_type="search_query"``,
so the model accounts for the fact that queries are short/incomplete while
documents are long/declarative. Both sides land in the same 1024-dim space.

- Model: embed-multilingual-v3.0 (Sanskrit/Hindi/English) — from settings.
- Batching: documents are embedded in groups of 96 (Cohere's per-call cap).
- Resilience: transient errors / rate limits are retried with exponential
  backoff. A monthly/trial *quota* 429 is not transient — it raises
  CohereQuotaExhausted immediately instead of burning minutes on retries.
- Optional disk cache (``enable_embedding_cache``), keyed by model +
  input_type + exact text. Off by default; the eval turns it on so reruns
  over the same questions don't spend Cohere calls. (src/utils/cache.py is an
  unimplemented Redis *response* cache stub, so it isn't reused here.)

Build this in: Phase 2, Step 5
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from pathlib import Path
from typing import Any

from config.settings import settings

logger = logging.getLogger(__name__)

# Cohere accepts at most 96 texts per embed call.
MAX_BATCH = 96
# Retry policy for transient failures / rate limits.
MAX_RETRIES = 6
BASE_BACKOFF = 2.0  # seconds; doubles each retry
# On a 429 (rate limit), wait at least this long — the trial limit is a rolling
# per-minute window, so short backoffs don't clear it.
RATE_LIMIT_WAIT = 62.0
# Rough token estimate for client-side throttling (~4 chars/token).
_CHARS_PER_TOKEN = 4

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EMBED_CACHE_PATH = PROJECT_ROOT / "data" / "cache" / "embedding_cache.json"

_client = None
# Disk embedding cache: key -> vector. None = disabled.
_cache: dict[str, list[float]] | None = None
_cache_path: Path | None = None
_cache_dirty = False
# Rolling log of (timestamp, estimated_tokens) for the trailing-60s throttle.
_token_log: list[tuple[float, int]] = []


def _get_client():
    """Lazily construct and cache the Cohere client."""
    global _client
    if _client is not None:
        return _client
    import cohere

    if not settings.cohere_api_key:
        raise RuntimeError(
            "COHERE_API_KEY is not set. Add it to .env before embedding."
        )
    _client = cohere.Client(api_key=settings.cohere_api_key)
    return _client


def _batched(items: list[Any], size: int):
    """Yield successive `size`-length slices of items."""
    for i in range(0, len(items), size):
        yield items[i:i + size]


def _estimate_tokens(texts: list[str]) -> int:
    return sum(len(t) for t in texts) // _CHARS_PER_TOKEN + 1


class CohereQuotaExhausted(RuntimeError):
    """The Cohere key's monthly/trial call quota is used up; retrying won't help."""


def _is_rate_limit(exc: Exception) -> bool:
    s = str(exc).lower()
    return "429" in s or "rate limit" in s or "too many requests" in s


def _is_quota_exhausted(exc: Exception) -> bool:
    """True for a 429 caused by the monthly quota (e.g. "1000 API calls / month"),
    as opposed to the per-minute limit that clears with backoff."""
    s = str(exc).lower()
    return _is_rate_limit(exc) and ("/ month" in s or "per month" in s or "monthly" in s)


def raise_if_quota_exhausted(exc: Exception, operation: str) -> None:
    """Re-raise a monthly-quota 429 as CohereQuotaExhausted with a clear message."""
    if _is_quota_exhausted(exc):
        raise CohereQuotaExhausted(
            f"Cohere {operation} failed: the API key's monthly call quota is exhausted "
            f"(trial keys allow 1000 calls/month). Wait for the quota to reset or use a "
            f"production key. Original error: {exc}"
        ) from exc


def _throttle(est_tokens: int) -> None:
    """Sleep so the trailing-60s token usage stays under the configured cap."""
    cap = settings.cohere_tokens_per_min
    if cap <= 0:
        return
    while True:
        now = time.time()
        # Drop entries older than 60s.
        while _token_log and now - _token_log[0][0] > 60:
            _token_log.pop(0)
        used = sum(t for _, t in _token_log)
        if used + est_tokens <= cap or not _token_log:
            break
        # Wait until the oldest entry ages out of the window.
        sleep_for = 60 - (now - _token_log[0][0]) + 0.5
        logger.info("Throttling embeddings: %d tok used in last 60s, "
                    "sleeping %.1fs to stay under %d/min.", used, sleep_for, cap)
        time.sleep(max(sleep_for, 1.0))
    _token_log.append((time.time(), est_tokens))


def _embed_with_retry(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed one batch (<= MAX_BATCH texts) with throttling + backoff."""
    client = _get_client()
    _throttle(_estimate_tokens(texts))
    last_exc: Exception | None = None
    for attempt in range(MAX_RETRIES):
        try:
            resp = client.embed(
                texts=texts,
                model=settings.embedding_model,
                input_type=input_type,
                embedding_types=["float"],
            )
            # cohere v5: resp.embeddings.float ; older shape: resp.embeddings
            embeddings = getattr(resp.embeddings, "float", None)
            if embeddings is None:
                embeddings = resp.embeddings
            return [list(vec) for vec in embeddings]
        except Exception as exc:  # noqa: BLE001 — Cohere raises varied error types
            last_exc = exc
            raise_if_quota_exhausted(exc, "embed")
            # Rate-limit errors need a full per-minute window; others back off.
            wait = RATE_LIMIT_WAIT if _is_rate_limit(exc) else BASE_BACKOFF * (2 ** attempt)
            logger.warning(
                "Cohere embed failed (attempt %d/%d): %s — retrying in %.1fs",
                attempt + 1, MAX_RETRIES, exc, wait,
            )
            time.sleep(wait)
    raise RuntimeError(
        f"Cohere embedding failed after {MAX_RETRIES} attempts: {last_exc}"
    )


def enable_embedding_cache(path: str | Path = DEFAULT_EMBED_CACHE_PATH) -> None:
    """Turn on the disk embedding cache, loading any existing entries."""
    global _cache, _cache_path, _cache_dirty
    _cache_path = Path(path)
    _cache = {}
    if _cache_path.exists():
        with open(_cache_path, "r", encoding="utf-8") as f:
            _cache = json.load(f)
    _cache_dirty = False
    logger.info("Embedding cache enabled (%d entries) at %s.", len(_cache), _cache_path)


def save_embedding_cache() -> None:
    """Write the disk embedding cache if it gained entries."""
    global _cache_dirty
    if _cache is None or _cache_path is None or not _cache_dirty:
        return
    _cache_path.parent.mkdir(parents=True, exist_ok=True)
    with open(_cache_path, "w", encoding="utf-8") as f:
        json.dump(_cache, f)
    _cache_dirty = False
    logger.info("Saved embedding cache (%d entries) to %s.", len(_cache), _cache_path)


def disable_embedding_cache() -> None:
    """Turn the disk embedding cache off (does not save)."""
    global _cache, _cache_path, _cache_dirty
    _cache, _cache_path, _cache_dirty = None, None, False


def _cache_key(text: str, input_type: str) -> str:
    raw = f"{settings.embedding_model}|{input_type}|{text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _embed_cached(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed texts, serving hits from the disk cache and embedding only misses."""
    global _cache_dirty
    if _cache is None:
        return _embed_uncached(texts, input_type)
    keys = [_cache_key(t, input_type) for t in texts]
    misses = [i for i, k in enumerate(keys) if k not in _cache]
    if misses:
        fresh = _embed_uncached([texts[i] for i in misses], input_type)
        for i, vec in zip(misses, fresh):
            _cache[keys[i]] = vec
        _cache_dirty = True
    logger.debug("Embedding cache: %d hit(s), %d miss(es).", len(texts) - len(misses), len(misses))
    return [_cache[k] for k in keys]


def _embed_uncached(texts: list[str], input_type: str) -> list[list[float]]:
    """Embed texts in batches of MAX_BATCH (no cache)."""
    vectors: list[list[float]] = []
    total_batches = (len(texts) + MAX_BATCH - 1) // MAX_BATCH
    for bi, batch in enumerate(_batched(texts, MAX_BATCH), start=1):
        if input_type == "search_document":
            logger.info("Embedding documents: batch %d/%d (%d texts).",
                        bi, total_batches, len(batch))
        vectors.extend(_embed_with_retry(batch, input_type))
    return vectors


def embed_documents(texts: list[str]) -> list[list[float]]:
    """Embed document texts (input_type='search_document').

    Batches internally in groups of 96 and returns one 1024-dim vector per
    input text, in the same order.
    """
    if not texts:
        return []
    vectors = _embed_cached(texts, "search_document")
    if vectors and len(vectors[0]) != settings.embedding_dimensions:
        logger.warning("Embedding dim %d != configured %d.",
                       len(vectors[0]), settings.embedding_dimensions)
    return vectors


def embed_query(query: str) -> list[float]:
    """Embed a single query (input_type='search_query'). Returns one vector."""
    if not query or not query.strip():
        raise ValueError("Cannot embed an empty query.")
    return _embed_cached([query], "search_query")[0]


def embed_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach an ``embedding`` field to each chunk dict.

    Args:
        chunks: Child chunk dicts with a ``text`` field.

    Returns:
        The same chunk dicts, each with a new ``embedding`` key (in place).
    """
    texts = [c.get("text", "") for c in chunks]
    vectors = embed_documents(texts)
    for chunk, vec in zip(chunks, vectors):
        chunk["embedding"] = vec
    return chunks
