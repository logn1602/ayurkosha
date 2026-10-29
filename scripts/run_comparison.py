"""
AyurKosha — Clean Retrieval Comparison
Runs the retrieval eval for several configurations, N runs each, interleaved
round-robin (so quota/latency drift hits every config equally), and prints
mean and spread (min–max) per metric.

Configs:
  rrf          RRF-fused semantic + BM25 only (no rerank)
  rerank       + Cohere rerank            (the eval baseline)
  rerank_mmr   + Cohere rerank + MMR      (what generation sees)
  rerank_hyde  rerank pipeline + HyDE passage (compare against "rerank")

Default is a DRY RUN: prints the plan and the estimated Cohere / Claude call
counts, then exits. Pass --run to execute. Aborts on the first INVALID run
(rerank skipped) or exhausted Cohere quota.

Run: python scripts/run_comparison.py            # plan + estimate only
     python scripts/run_comparison.py --run      # execute
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

from src.evaluation.run_eval import DEFAULT_DATASET, DEFAULT_OUTPUT_DIR, load_dataset, run_eval
from src.ingestion import embedder

CONFIGS = {
    "rrf": {"pipeline": "rrf", "use_hyde": False},
    "rerank": {"pipeline": "rerank", "use_hyde": False},
    "rerank_mmr": {"pipeline": "rerank_mmr", "use_hyde": False},
    "rerank_hyde": {"pipeline": "rerank", "use_hyde": True},
}
METRICS = ("hit_rate", "recall_at_k", "mrr")


def estimate_calls(configs: list[str], runs: int, n_questions: int, cached_queries: int) -> dict:
    """Estimate API calls for the plan (embedding cache on).

    Per question: query embed (once ever — cached afterwards, shared by every
    config; MMR needs none since it uses rerank scores); rerank (every run, every config but
    rrf); MMR candidate embed batch (first rerank_mmr run only — candidates are
    deterministic, so later runs hit the cache); HyDE passage embed + Claude
    call (every hyde run — passages differ per run, so they never hit).
    """
    cohere = {"query_embed": max(0, n_questions - cached_queries), "rerank": 0,
              "mmr_embed": 0, "hyde_embed": 0}
    claude = 0
    for name in configs:
        cfg = CONFIGS[name]
        if cfg["pipeline"] != "rrf":
            cohere["rerank"] += runs * n_questions
        if cfg["pipeline"] == "rerank_mmr":
            cohere["mmr_embed"] += n_questions
        if cfg["use_hyde"]:
            cohere["hyde_embed"] += runs * n_questions
            claude += runs * n_questions
    cohere["total"] = sum(cohere.values())
    return {"cohere": cohere, "claude_haiku": claude}


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
            cells.append(f"{statistics.mean(vals):.3f} ({min(vals):.3f}–{max(vals):.3f})")
        lines.append(f"{name:<12} " + "  ".join(f"{c:>22}" for c in cells))
    return lines


def main():
    parser = argparse.ArgumentParser(description="Clean multi-config retrieval comparison.")
    parser.add_argument("--configs", nargs="+", choices=list(CONFIGS), default=list(CONFIGS))
    parser.add_argument("--runs", type=int, default=3, help="Runs per config (default 3).")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET))
    parser.add_argument("--run", action="store_true", help="Execute (default: dry run).")
    args = parser.parse_args()

    questions = [item["question"] for item in load_dataset(args.dataset)]
    est = estimate_calls(args.configs, args.runs, len(questions), _count_cached_queries(questions))
    print("AyurKosha — Clean Retrieval Comparison")
    print("=" * 50)
    print(f"Configs: {', '.join(args.configs)}  |  Runs each: {args.runs}  |  "
          f"Questions: {len(questions)}")
    print(f"Estimated Cohere calls: {est['cohere']['total']}  {est['cohere']}")
    print(f"Estimated Claude (Haiku) calls: {est['claude_haiku']}")
    if not args.run:
        print("\nDry run — pass --run to execute.")
        return

    logging.basicConfig(level=logging.WARNING, format="%(asctime)s %(levelname)s %(message)s",
                        datefmt="%H:%M:%S")
    rows: dict[str, list[dict]] = {name: [] for name in args.configs}
    files: dict[str, list[str]] = {name: [] for name in args.configs}
    for round_no in range(1, args.runs + 1):
        for name in args.configs:
            payload = run_eval(dataset_path=args.dataset, mode="retrieval", **CONFIGS[name])
            print(f"round {round_no} {name:<12} {payload['status']}  {payload['summary']['retrieval']}")
            if payload["status"] != "VALID":
                sys.exit(f"Aborting: {name} run {round_no} is INVALID "
                         f"({payload['summary']['rerank_skips']} rerank skips).")
            rows[name].append(payload["summary"])
            files[name].append(payload["saved_to"])

    print("\nRESULTS — mean (min–max)")
    print("\n".join(_summarize(rows)))
    out = Path(DEFAULT_OUTPUT_DIR) / f"comparison_{datetime.now():%Y%m%d_%H%M%S}.json"
    out.write_text(json.dumps({"runs": args.runs, "summaries": rows, "files": files},
                              ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nSaved to: {out}")


if __name__ == "__main__":
    main()
