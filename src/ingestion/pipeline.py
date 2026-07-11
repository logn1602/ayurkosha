"""
AyurKosha — Ingestion Pipeline Orchestrator
Wires all offline ingestion steps into a single run_ingestion() call.

Flow (offline, one-time per document set):

    data/raw/*  ->  loaders     (PDF/DOCX/MD/HTML -> page records)
                ->  metadata    (text_name, sthana/chapter, monograph fields)
                ->  chunkers    (parent + child chunks)
                ->  embedder    (Cohere search_document vectors, batches of 96)
                ->  pinecone_store (upsert child vectors + metadata, batches of 100)
                +   bm25_store  (serialize keyword index over children)
                +   parent_store(serialize child->parent context map)

At query time nothing here runs again — searches hit the pre-built indexes.

`max_files` / `max_pages` bound the work for a cheap first validation run
before committing to a full (paid) ingest of the whole corpus.

Build this in: Phase 2, Step 9
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from config.settings import settings
from src.ingestion import loaders, metadata, chunkers, bm25_store, parent_store

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _iter_source_files(root: Path):
    for path in sorted(root.glob("**/*")):
        if path.is_file() and path.suffix.lower() in loaders.SUPPORTED_EXTENSIONS:
            yield path


def run_ingestion(
    data_dir: str | Path = None,
    max_files: int | None = None,
    max_pages: int | None = None,
    embed: bool = True,
    upsert: bool = True,
    skip_existing: bool = True,
) -> dict[str, Any]:
    """Run the full offline ingestion pipeline.

    Args:
        data_dir: Root to scan (default data/raw).
        max_files: If set, process at most this many source files (cheap runs).
        max_pages: If set, keep at most this many page-records per file.
        embed: If False, skip Cohere embedding (build BM25/parent stores only —
            useful for a no-cost dry run).
        upsert: If False, embed but skip the Pinecone upsert.
        skip_existing: If True (and upserting), skip chunks whose ids are already
            in Pinecone so an interrupted run resumes cheaply without re-embedding.

    Returns:
        Stats dict: files, pages, parents, children, embedded, upserted,
        skipped, seconds.
    """
    root = Path(data_dir) if data_dir else PROJECT_ROOT / "data" / "raw"
    if not root.is_dir():
        raise FileNotFoundError(f"Data directory not found: {root}")

    start = time.time()
    stats = {"files": 0, "pages": 0, "parents": 0, "children": 0,
             "embedded": 0, "upserted": 0, "skipped": 0}

    # ── 1-3: load -> enrich metadata -> chunk (per file) ──────────────
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for path in _iter_source_files(root):
        if max_files is not None and stats["files"] >= max_files:
            break
        records = loaders.load_document(path, max_pages=max_pages)
        if not records:
            continue
        metadata.enrich_records(records)
        chunked = chunkers.chunk_records(records)
        all_parents.extend(chunked["parents"])
        all_children.extend(chunked["children"])
        stats["files"] += 1
        stats["pages"] += len(records)
        logger.info("Ingested %s: %d pages -> %d parents, %d children.",
                    path.name, len(records),
                    len(chunked["parents"]), len(chunked["children"]))

    stats["parents"] = len(all_parents)
    stats["children"] = len(all_children)

    if not all_children:
        logger.warning("No children produced; nothing to index.")
        stats["seconds"] = round(time.time() - start, 1)
        return stats

    # ── 8: parent store (no API cost) ─────────────────────────────────
    pstore = parent_store.build_parent_store(all_parents)
    parent_store.save_parent_store(pstore)

    # ── 7: BM25 store (no API cost) ───────────────────────────────────
    bm25 = bm25_store.build_bm25_index(all_children)
    bm25_store.save_bm25_index(bm25)

    # ── 5+6: embed (Cohere) and upsert (Pinecone) ─────────────────────
    # Stream in batches so Pinecone fills incrementally (durable progress on
    # large runs) and we never hold all embeddings in memory at once.
    if embed:
        from src.ingestion import embedder

        if upsert:
            from src.ingestion import pinecone_store
            index = pinecone_store.ensure_index()
            batch_size = embedder.MAX_BATCH  # 96 (Cohere per-call cap)
            n = len(all_children)
            for i in range(0, n, batch_size):
                batch = all_children[i:i + batch_size]
                if skip_existing:
                    have = pinecone_store.fetch_existing_ids(
                        [c["chunk_id"] for c in batch], index=index)
                    if have:
                        stats["skipped"] += len(have)
                        batch = [c for c in batch if c["chunk_id"] not in have]
                if batch:
                    vecs = embedder.embed_documents([c.get("text", "") for c in batch])
                    for c, v in zip(batch, vecs):
                        c["embedding"] = v
                    stats["embedded"] += len(vecs)
                    stats["upserted"] += pinecone_store.upsert_chunks(batch, index=index)
                    for c in batch:        # free embeddings to bound memory
                        c.pop("embedding", None)
                logger.info("Embed+upsert progress: %d/%d children (skipped %d).",
                            min(i + batch_size, n), n, stats["skipped"])
        else:
            embedder.embed_chunks(all_children)
            stats["embedded"] = sum(1 for c in all_children if c.get("embedding"))

    stats["seconds"] = round(time.time() - start, 1)
    logger.info("Ingestion complete: %s", stats)
    return stats
