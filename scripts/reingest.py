"""
AyurKosha — Re-ingestion (blue/green)
Rebuilds the whole index with the current corpus settings (font map, folding,
glued-word splitting, contextual headers, source exclusions) into a NEW
Pinecone index, then promotes the matching local stores.

Why a new index instead of rebuilding in place:
  - every vector must be re-embedded (headers change the embedded text), and
    serverless Pinecone can't delete by metadata filter, so stale vectors of
    excluded sources couldn't be cleaned out in place;
  - in an empty index, skip_existing makes the run resumable for free: if it
    stops (e.g. Cohere quota), re-running the same command embeds only what's
    missing;
  - the live index and stores stay untouched until the new build is complete.

DEFAULT IS A DRY RUN: offline, no API calls, nothing written. It builds the
corpus exactly as the run would and prints the plan: files included/excluded,
chunk counts, Cohere embed calls, tokens and time.

  python scripts/reingest.py                            # dry run (plan only)
  python scripts/reingest.py --run --index ayurkosha-v2 # execute

--run steps:
  1. build the corpus; write BM25 + parent stores to data/cache/staging/<index>/
  2. create the target index if needed; embed + upsert (skips ids already there)
  3. verify the target's vector count matches the chunk count
  4. back up data/cache/{bm25_index.pkl,parent_store.json} to
     data/cache/backup_<timestamp>/ and promote the staged stores
  5. print the .env change that switches the app to the new index
"""

import argparse
import logging
import math
import shutil
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from config.settings import settings
from src.ingestion import bm25_store, parent_store
from src.ingestion.context_headers import contextual_text
from src.ingestion.embedder import MAX_BATCH, CohereQuotaExhausted
from src.ingestion.pipeline import PROJECT_ROOT, build_corpus, run_ingestion

CACHE_DIR = PROJECT_ROOT / "data" / "cache"
STORE_FILES = (bm25_store.DEFAULT_INDEX_PATH.name, parent_store.DEFAULT_STORE_PATH.name)
TRIAL_CALLS_PER_MONTH = 1000
COMPARISON_CALLS = 420          # scripts/run_comparison.py estimate, 4 configs x 3 runs
FLAGS = ("apply_font_char_map", "bm25_fold_diacritics", "split_glued_ocr_words", "contextual_chunk_headers",
         "exclude_charaka", "exclude_ah_srikantha_murthy", "exclude_ah_sanskrit_commentaries")


def plan(corpus: dict) -> dict:
    """Embed-call / token / time estimate for embedding every child once."""
    children = corpus["children"]
    chars = sum(len(contextual_text(c)) for c in children)
    tokens = chars / 4                      # ~4 chars/token; undercounts Devanagari
    calls = math.ceil(len(children) / MAX_BATCH)
    minutes = tokens / settings.cohere_tokens_per_min if settings.cohere_tokens_per_min > 0 else 0.0
    return {"children": len(children), "embed_calls": calls, "tokens": int(tokens), "minutes": minutes}


def print_plan(corpus: dict, estimate: dict, index_name: str) -> None:
    print("AyurKosha — Re-ingestion plan")
    print("=" * 60)
    print("Settings: " + ", ".join(f"{f}={getattr(settings, f)}" for f in FLAGS))
    print("\nSource files:")
    for name, n in corpus["per_source"].items():
        print(f"  INCLUDE {name:46} pages={n['pages']:5} parents={n['parents']:5} children={n['children']:6}")
    for name, reason in corpus["excluded"]:
        print(f"  EXCLUDE {name:46} {reason}")
    s = corpus["stats"]
    print(f"\nTotals: {s['files']} files, {s['pages']} pages, {s['parents']} parents, {s['children']} children")
    with_header = sum(1 for c in corpus["children"] if c["metadata"].get("context_header"))
    split = sum(1 for c in corpus["children"] if c.get("bm25_text"))
    print(f"Contextual headers: {with_header}/{s['children']} children | BM25 split text: {split}/{s['children']}")
    print(f"\nCohere embed calls: {estimate['embed_calls']} (batches of {MAX_BATCH}) | "
          f"~{estimate['tokens'] / 1e6:.1f}M tokens | ~{estimate['minutes']:.0f} min at "
          f"{settings.cohere_tokens_per_min} tokens/min")
    total = estimate["embed_calls"] + COMPARISON_CALLS
    print(f"Quota: trial keys allow {TRIAL_CALLS_PER_MONTH} calls/month; this run + the clean comparison "
          f"(~{COMPARISON_CALLS}) = ~{total}. No Claude calls.")
    print(f"\nTarget Pinecone index: {index_name}  (live index '{settings.pinecone_index_name}' is not touched)")
    by_work = Counter()
    print("Sample headers:")
    for c in corpus["children"]:
        h = c["metadata"].get("context_header")
        work = c["metadata"].get("text_name")
        if h and by_work[work] < 2 and h.count(" > ") >= 1:
            by_work[work] += 1
            print(f"  {c['chunk_id']:52} {h}")


def promote_stores(staging: Path, cache: Path | None = None) -> Path:
    """Back up the live stores, then copy the staged ones into place. Returns the backup dir."""
    cache = cache or CACHE_DIR          # resolved at call time, never bound at import
    backup = cache / f"backup_{datetime.now():%Y%m%d_%H%M%S}"
    backup.mkdir(parents=True, exist_ok=False)
    for name in STORE_FILES:
        if (cache / name).exists():
            shutil.copy2(cache / name, backup / name)
    for name in STORE_FILES:
        shutil.copy2(staging / name, cache / name)
    return backup


def _vector_count(index) -> int:
    stats = index.describe_index_stats()
    count = stats.get("total_vector_count") if isinstance(stats, dict) else getattr(stats, "total_vector_count", None)
    return int(count or 0)


def run(index_name: str, data_dir=None) -> int:
    if index_name == settings.pinecone_index_name:
        print(f"Refusing to rebuild the live index '{index_name}' in place. Pass a new name, "
              f"e.g. --index {settings.pinecone_index_name}-v2, and switch to it afterwards.", file=sys.stderr)
        return 1
    from src.ingestion import pinecone_store

    staging = CACHE_DIR / "staging" / index_name
    staging.mkdir(parents=True, exist_ok=True)
    try:
        index = pinecone_store.ensure_index(index_name)
    except Exception as exc:  # noqa: BLE001 — e.g. plan index limit
        print(f"Could not create/open Pinecone index '{index_name}': {exc}\n"
              "If your plan's index limit is reached, delete an unused index or reuse an empty one.",
              file=sys.stderr)
        return 1
    print(f"Target '{index_name}' holds {_vector_count(index)} vectors before this run "
          "(non-zero means resuming; existing ids are skipped).")

    try:
        stats = run_ingestion(data_dir=data_dir, embed=True, upsert=True, skip_existing=True,
                              index_name=index_name, store_dir=staging)
    except CohereQuotaExhausted as exc:
        print(f"\nStopped: {exc}\nNothing is lost: re-run the same command after the quota resets and "
              "only the missing chunks are embedded. The live index and stores are untouched.", file=sys.stderr)
        return 2
    print(f"\nIngestion stats: {stats}")

    expected = stats["children"]
    count = 0
    for _ in range(12):                       # serverless stats are eventually consistent
        count = _vector_count(index)
        if count >= expected:
            break
        time.sleep(5)
    if count < expected:
        print(f"Target holds {count} vectors but the corpus has {expected} chunks. Stores NOT promoted. "
              "Re-run the same command to fill the gap.", file=sys.stderr)
        return 3

    backup = promote_stores(staging)
    print(f"\nDone: '{index_name}' holds {count} vectors; staged stores promoted to {CACHE_DIR}.")
    print(f"Previous stores backed up to {backup}.")
    print("\nNext: switch the app to the new index by setting this line in .env:")
    print(f"  PINECONE_INDEX_NAME={index_name}")
    print(f"Rollback: copy the files in {backup.name}/ back into data/cache/ and restore the old "
          f"PINECONE_INDEX_NAME ('{settings.pinecone_index_name}').")
    return 0


def main():
    parser = argparse.ArgumentParser(description="Blue/green re-ingestion (dry run by default).")
    parser.add_argument("--run", action="store_true", help="Execute (default: offline dry run).")
    parser.add_argument("--index", default=f"{settings.pinecone_index_name}-v2",
                        help="Target Pinecone index (must differ from the live one).")
    parser.add_argument("--data-dir", default=None, help="Source root (default data/raw).")
    parser.add_argument("--max-files", type=int, default=None, help="Dry run only: limit files.")
    parser.add_argument("--max-pages", type=int, default=None, help="Dry run only: limit pages per file.")
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    if args.run:
        if args.max_files or args.max_pages:
            parser.error("--max-files/--max-pages are dry-run only (a partial build must not be promoted).")
        logging.getLogger("src.ingestion.pipeline").setLevel(logging.INFO)
        sys.exit(run(args.index, data_dir=args.data_dir))

    corpus = build_corpus(args.data_dir, max_files=args.max_files, max_pages=args.max_pages)
    print_plan(corpus, plan(corpus), args.index)
    print("\nDRY RUN: nothing written, no API calls. To execute:")
    print(f"  python scripts/reingest.py --run --index {args.index}")


if __name__ == "__main__":
    main()
