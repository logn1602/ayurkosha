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
from src.ingestion import loaders, metadata, chunkers, bm25_store, parent_store, text_cleanup
from src.ingestion.context_headers import annotate_context, contextual_text

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def excluded_reason(filename: str) -> str | None:
    """Why a source file is skipped at ingestion (per the exclude_* settings), or None."""
    name = filename.lower()
    if settings.exclude_charaka and metadata.infer_text_name(name) == "Charaka Samhita":
        return "exclude_charaka: English translation OCR'd as Devanagari; needs re-OCR"
    if settings.exclude_ah_srikantha_murthy and name.startswith("ashtanga_hridaya_srikantha_murthy"):
        return "exclude_ah_srikantha_murthy: English book OCR'd with a Hindi engine (unusable text layer)"
    if settings.exclude_ah_sanskrit_commentaries and name.startswith("ashtanga_hridaya_sanskrit_commentaries"):
        return "exclude_ah_sanskrit_commentaries: Devanagari-only; English queries can't match it"
    return None


def _iter_source_files(root: Path):
    for path in sorted(root.glob("**/*")):
        if path.is_file() and path.suffix.lower() in loaders.SUPPORTED_EXTENSIONS:
            yield path


def build_corpus(
    data_dir: str | Path = None,
    max_files: int | None = None,
    max_pages: int | None = None,
) -> dict[str, Any]:
    """Load -> repair -> enrich -> annotate -> chunk every included source file.

    Offline and side-effect free: no network calls, nothing written. This is
    the exact chunking an ingestion would index, so a dry run can inspect it.

    Returns:
        {"parents", "children", "stats", "per_source", "excluded"}, where
        per_source maps filename -> {"pages", "parents", "children"} and
        excluded lists (filename, reason) pairs.
    """
    root = Path(data_dir) if data_dir else PROJECT_ROOT / "data" / "raw"
    if not root.is_dir():
        raise FileNotFoundError(f"Data directory not found: {root}")

    stats = {"files": 0, "pages": 0, "parents": 0, "children": 0, "excluded_files": 0}
    per_source: dict[str, dict[str, int]] = {}
    excluded: list[tuple[str, str]] = []
    all_parents: list[dict[str, Any]] = []
    all_children: list[dict[str, Any]] = []

    for path in _iter_source_files(root):
        if max_files is not None and stats["files"] >= max_files:
            break
        reason = excluded_reason(path.name)
        if reason:
            logger.info("Skipping %s (%s).", path.name, reason)
            stats["excluded_files"] += 1
            excluded.append((path.name, reason))
            continue
        records = loaders.load_document(path, max_pages=max_pages)
        if not records:
            continue
        text_cleanup.apply_font_fixes(records)   # before enrichment: headings/properties see IAST
        metadata.enrich_records(records)
        annotate_context(records)                # [Work] > [Section] > [Item] markers, if enabled
        chunked = chunkers.chunk_records(records)
        all_parents.extend(chunked["parents"])
        all_children.extend(chunked["children"])
        stats["files"] += 1
        stats["pages"] += len(records)
        per_source[path.name] = {"pages": len(records), "parents": len(chunked["parents"]),
                                 "children": len(chunked["children"])}
        logger.info("Ingested %s: %d pages -> %d parents, %d children.",
                    path.name, len(records),
                    len(chunked["parents"]), len(chunked["children"]))

    text_cleanup.add_bm25_text(all_children)   # glue-split matching text, if enabled
    stats["parents"] = len(all_parents)
    stats["children"] = len(all_children)
    return {"parents": all_parents, "children": all_children, "stats": stats,
            "per_source": per_source, "excluded": excluded}


def run_ingestion(
    data_dir: str | Path = None,
    max_files: int | None = None,
    max_pages: int | None = None,
    embed: bool = True,
    upsert: bool = True,
    skip_existing: bool = True,
    index_name: str | None = None,
    store_dir: str | Path | None = None,
) -> dict[str, Any]:
    """Run the full offline ingestion pipeline.

    Args:
        data_dir: Root to scan (default data/raw).
        max_files: If set, process at most this many source files (cheap runs).
        max_pages: If set, keep at most this many page-records per file.
        embed: If False, skip Cohere embedding (build BM25/parent stores only).
        upsert: If False, embed but skip the Pinecone upsert.
        skip_existing: If True (and upserting), skip chunks whose ids are already
            in Pinecone so an interrupted run resumes cheaply without re-embedding.
        index_name: Pinecone index to write (default settings.pinecone_index_name).
        store_dir: Directory for the BM25 / parent stores (default data/cache).

    Returns:
        Stats dict: files, pages, parents, children, excluded_files, embedded,
        upserted, skipped, seconds.
    """
    start = time.time()
    corpus = build_corpus(data_dir, max_files=max_files, max_pages=max_pages)
    all_parents, all_children = corpus["parents"], corpus["children"]
    stats = {**corpus["stats"], "embedded": 0, "upserted": 0, "skipped": 0}

    if not all_children:
        logger.warning("No children produced; nothing to index.")
        stats["seconds"] = round(time.time() - start, 1)
        return stats

    # ── parent store + BM25 store (no API cost) ───────────────────────
    pstore_path = Path(store_dir) / parent_store.DEFAULT_STORE_PATH.name if store_dir else parent_store.DEFAULT_STORE_PATH
    bm25_path = Path(store_dir) / bm25_store.DEFAULT_INDEX_PATH.name if store_dir else bm25_store.DEFAULT_INDEX_PATH
    parent_store.save_parent_store(parent_store.build_parent_store(all_parents), pstore_path)
    bm25_store.save_bm25_index(bm25_store.build_bm25_index(all_children), bm25_path)

    # ── embed (Cohere) and upsert (Pinecone) ──────────────────────────
    # Stream in batches so Pinecone fills incrementally (durable progress on
    # large runs) and we never hold all embeddings in memory at once.
    if embed:
        from src.ingestion import embedder

        if upsert:
            from src.ingestion import pinecone_store
            index = pinecone_store.ensure_index(index_name)
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
                    vecs = embedder.embed_documents([contextual_text(c) for c in batch])
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
