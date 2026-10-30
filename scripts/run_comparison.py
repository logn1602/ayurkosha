"""
AyurKosha — Clean Retrieval Comparison (before / after re-ingestion)
Runs the retrieval eval per configuration and prints hit rate, Recall@k and
MRR. Two phases bracket the re-ingestion (scripts/reingest.py):

  before   OLD index + OLD local stores, NEW labels, every new text flag OFF
           (font map, folding + romanization keys, glued-word split, headers),
           so queries tokenize the way the old index was built.
           Configs: rrf, rerank.
  after    NEW index + NEW stores, flags as configured (on).
           Configs: rrf, rerank, rerank_mmr, rerank_hyde.

Clean runs are deterministic (identical across repeats), so every config runs
once; only HyDE configs repeat (--hyde-runs, default 3), because Claude's
passages vary run to run.

Before running, the phase is checked against the data it would read: the
Pinecone vector count must equal the local BM25 chunk count, and the stores
must be the right generation (old: no context headers; new: headers). A
mismatch, e.g. new stores with the old index, aborts.

Default is a DRY RUN: offline, prints the phase plan, the call estimate and
the full budget (before + re-ingest + after). Pass --run to execute. Aborts
on the first INVALID run (rerank skipped) or an exhausted Cohere quota.

Run: python scripts/run_comparison.py --phase before          # plan only
     python scripts/run_comparison.py --phase before --run
     python scripts/run_comparison.py --phase after --run
"""

import argparse
import json
import logging
import statistics
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from config.settings import settings
from src.evaluation.run_eval import DEFAULT_DATASET, DEFAULT_OUTPUT_DIR, load_dataset, run_eval
from src.ingestion import embedder

CONFIGS = {
    "rrf": {"pipeline": "rrf", "use_hyde": False},
    "rerank": {"pipeline": "rerank", "use_hyde": False},
    "rerank_mmr": {"pipeline": "rerank_mmr", "use_hyde": False},
    "rerank_hyde": {"pipeline": "rerank", "use_hyde": True},
}
PHASES = {
    "before": ["rrf", "rerank"],
    "after": ["rrf", "rerank", "rerank_mmr", "rerank_hyde"],
}
# The flags whose effect the old index predates; all forced off in "before".
NEW_TEXT_FLAGS = ("apply_font_char_map", "bm25_fold_diacritics", "split_glued_ocr_words",
                  "contextual_chunk_headers")
# From the scripts/reingest.py dry run on 2026-10-29 (7 files, 22,718 chunks).
REINGEST_EMBED_CALLS = 237
TRIAL_CALLS_PER_MONTH = 1000
METRICS = ("hit_rate", "recall_at_k", "mrr")


def runs_for(config: str, hyde_runs: int) -> int:
    return hyde_runs if CONFIGS[config]["use_hyde"] else 1


def estimate_calls(configs: list[str], n_questions: int, cached_queries: int, hyde_runs: int = 3) -> dict:
    """Estimate API calls for one phase (embedding cache on).

    Per question: query embed (once ever; cached afterwards and shared by every
    config and both phases); rerank (every run of every config but rrf); MMR
    candidate embed batch (first rerank_mmr run; MMR itself uses rerank scores,
    not a query embed); HyDE passage embed + Claude call (every HyDE run:
    passages differ per run, so they never hit the cache).
    """
    cohere = {"query_embed": max(0, n_questions - cached_queries), "rerank": 0, "mmr_embed": 0, "hyde_embed": 0}
    claude = 0
    for name in configs:
        cfg, runs = CONFIGS[name], runs_for(name, hyde_runs)
        if cfg["pipeline"] != "rrf":
            cohere["rerank"] += runs * n_questions
        if cfg["pipeline"] == "rerank_mmr":
            cohere["mmr_embed"] += n_questions
        if cfg["use_hyde"]:
            cohere["hyde_embed"] += runs * n_questions
            claude += runs * n_questions
    cohere["total"] = sum(cohere.values())
    return {"cohere": cohere, "claude_haiku": claude}


def full_budget(n_questions: int, cached_queries: int, hyde_runs: int = 3) -> dict:
    """Cohere calls for the whole sequence: before run -> re-ingest -> after run."""
    before = estimate_calls(PHASES["before"], n_questions, cached_queries, hyde_runs)
    after = estimate_calls(PHASES["after"], n_questions, n_questions, hyde_runs)   # queries cached by then
    total = before["cohere"]["total"] + REINGEST_EMBED_CALLS + after["cohere"]["total"]
    return {"before": before["cohere"]["total"], "reingest": REINGEST_EMBED_CALLS, "after": after["cohere"]["total"],
            "total": total, "margin": TRIAL_CALLS_PER_MONTH - total, "claude_haiku": after["claude_haiku"]}


COUNT_TOLERANCE = 0.005   # the live index holds 1 stray vector (46,827 vs 46,826 chunks)


def consistency_error(phase: str, n_vectors: int, n_chunks: int, stores_have_headers: bool) -> str | None:
    """Why the index/stores don't fit the phase, or None if they do.

    Counts must agree within COUNT_TOLERANCE: mixing builds differs by
    thousands (old 46,827 vectors vs new 22,718 chunks), a stray vector by one.
    """
    if abs(n_vectors - n_chunks) > COUNT_TOLERANCE * max(n_chunks, 1):
        return (f"Pinecone index '{settings.pinecone_index_name}' has {n_vectors} vectors but the local BM25 "
                f"store has {n_chunks} chunks: index and stores are from different builds.")
    if phase == "before" and stores_have_headers:
        return "The local stores are the NEW build (chunks carry context headers); 'before' needs the old ones."
    if phase == "after" and not stores_have_headers:
        return "The local stores are the OLD build (no context headers); run 'after' once reingest.py has promoted."
    return None


def _local_stores() -> tuple[int, bool]:
    from src.ingestion.bm25_store import load_bm25_index
    chunks = load_bm25_index().chunks
    return len(chunks), any(c.get("metadata", {}).get("context_header") for c in chunks)


def _index_vector_count(name: str) -> int:
    """Vector count of an existing index (never creates one)."""
    from src.ingestion import pinecone_store
    pc = pinecone_store._get_client()
    if name not in pinecone_store._index_names(pc):
        raise SystemExit(f"Pinecone index '{name}' does not exist (check PINECONE_INDEX_NAME in .env).")
    stats = pc.Index(name).describe_index_stats()
    count = stats.get("total_vector_count") if isinstance(stats, dict) else getattr(stats, "total_vector_count", 0)
    return int(count or 0)


def _count_cached_queries(questions: list[str]) -> int:
    path = embedder.DEFAULT_EMBED_CACHE_PATH
    if not path.exists():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        cache = json.load(f)
    return sum(1 for q in questions if embedder._cache_key(q, "search_query") in cache)


def _summarize(rows: dict[str, list[dict]]) -> list[str]:
    lines = [f"{'config':<12} " + "  ".join(f"{m:>22}" for m in METRICS)]
    for name, summaries in rows.items():
        cells = []
        for m in METRICS:
            vals = [s["retrieval"][m] for s in summaries]
            cells.append(f"{vals[0]:.3f}" if len(vals) == 1 else
                         f"{statistics.mean(vals):.3f} ({min(vals):.3f}–{max(vals):.3f})")
        lines.append(f"{name:<12} " + "  ".join(f"{c:>22}" for c in cells))
    return lines


def _latest(phase: str) -> dict | None:
    files = sorted(Path(DEFAULT_OUTPUT_DIR).glob(f"comparison_{phase}_*.json"))
    return json.loads(files[-1].read_text(encoding="utf-8")) if files else None


def main():
    parser = argparse.ArgumentParser(description="Before/after retrieval comparison (dry run by default).")
    parser.add_argument("--phase", choices=list(PHASES), required=True)
    parser.add_argument("--hyde-runs", type=int, default=3, help="Runs per HyDE config (others run once).")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--run", action="store_true", help="Execute (default: offline dry run).")
    args = parser.parse_args()

    if args.phase == "before":
        for flag in NEW_TEXT_FLAGS:
            setattr(settings, flag, False)
    configs = PHASES[args.phase]
    questions = [item["question"] for item in load_dataset(args.dataset)]
    cached = _count_cached_queries(questions)
    est = estimate_calls(configs, len(questions), cached, args.hyde_runs)
    budget = full_budget(len(questions), cached, args.hyde_runs)

    print(f"AyurKosha — Retrieval comparison, phase '{args.phase}'")
    print("=" * 60)
    print("Configs: " + ", ".join(f"{c} x{runs_for(c, args.hyde_runs)}" for c in configs)
          + f"  |  Questions: {len(questions)}  |  Index: {settings.pinecone_index_name}")
    print("Text flags: " + ", ".join(f"{f}={getattr(settings, f)}" for f in NEW_TEXT_FLAGS))
    print(f"This phase: Cohere {est['cohere']['total']} {est['cohere']} | Claude (Haiku) {est['claude_haiku']}")
    print(f"\nFull budget (Cohere calls): before {budget['before']} + re-ingest {budget['reingest']} + "
          f"after {budget['after']} = {budget['total']} of {TRIAL_CALLS_PER_MONTH}/month "
          f"-> margin {budget['margin']} ({budget['margin'] / TRIAL_CALLS_PER_MONTH:.0%}). "
          f"Claude: {budget['claude_haiku']} Haiku calls (HyDE).")
    if not args.run:
        print("\nDRY RUN: no API calls. Pass --run to execute.")
        return

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s", datefmt="%H:%M:%S")
    n_chunks, has_headers = _local_stores()
    err = consistency_error(args.phase, _index_vector_count(settings.pinecone_index_name), n_chunks, has_headers)
    if err:
        sys.exit(f"Aborting: {err}")

    rows: dict[str, list[dict]] = {name: [] for name in configs}
    files: dict[str, list[str]] = {name: [] for name in configs}
    for round_no in range(1, max(runs_for(c, args.hyde_runs) for c in configs) + 1):
        for name in configs:
            if round_no > runs_for(name, args.hyde_runs):
                continue
            payload = run_eval(dataset_path=args.dataset, mode="retrieval", **CONFIGS[name])
            print(f"round {round_no} {name:<12} {payload['status']}  {payload['summary']['retrieval']}")
            if payload["status"] != "VALID":
                sys.exit(f"Aborting: {name} run {round_no} is INVALID "
                         f"({payload['summary']['rerank_skips']} rerank skips).")
            rows[name].append(payload["summary"])
            files[name].append(payload["saved_to"])

    print(f"\nRESULTS ({args.phase}) — single run, or mean (min–max) over repeats")
    print("\n".join(_summarize(rows)))
    before = _latest("before") if args.phase == "after" else None
    if before:
        print("\nBEFORE (old index, old text) for comparison:")
        print("\n".join(_summarize(before["summaries"])))
    out = Path(DEFAULT_OUTPUT_DIR) / f"comparison_{args.phase}_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"phase": args.phase, "index": settings.pinecone_index_name,
                               "flags": {f: getattr(settings, f) for f in NEW_TEXT_FLAGS},
                               "hyde_runs": args.hyde_runs, "summaries": rows, "files": files},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to: {out}")


if __name__ == "__main__":
    main()
