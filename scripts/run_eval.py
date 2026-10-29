"""
AyurKosha — Run Evaluation Suite
CLI entry point for quality evaluation.

Run (retrieval only, free):  python scripts/run_eval.py --retrieval-only
Run (generation, needs $):   python scripts/run_eval.py --generation-only
Run (everything + judge):    python scripts/run_eval.py --judge
Default (retrieval + gen):   python scripts/run_eval.py
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure the project root is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 【N】 citation markers can appear in printed answers; force UTF-8 so the
# Windows console (cp1252) doesn't choke.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from src.evaluation.run_eval import (
    DEFAULT_DATASET,
    DEFAULT_OUTPUT_DIR,
    PIPELINES,
    run_eval,
)


def main():
    parser = argparse.ArgumentParser(description="Run the AyurKosha evaluation suite.")
    parser.add_argument("--dataset", default=str(DEFAULT_DATASET),
                        help="Path to the eval dataset JSON.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_DIR),
                        help="Directory for timestamped result files.")
    parser.add_argument("--retrieval-only", action="store_true",
                        help="Only retrieval metrics (no Anthropic cost).")
    parser.add_argument("--generation-only", action="store_true",
                        help="Only generation metrics (needs Anthropic credits).")
    parser.add_argument("--judge", action="store_true",
                        help="Also run the Claude LLM judge (needs credits).")
    parser.add_argument("--hyde", action="store_true",
                        help="Add a HyDE passage to semantic retrieval (one cheap Claude call per question).")
    parser.add_argument("--allow-rerank-skips", action="store_true",
                        help="Exit 0 even if some questions skipped rerank (run is still marked INVALID).")
    parser.add_argument("--no-embed-cache", action="store_true",
                        help="Don't use the disk embedding cache (data/cache/embedding_cache.json).")
    parser.add_argument("--pipeline", choices=PIPELINES, default="rerank",
                        help="Ranked list to score: RRF only, + Cohere rerank (default), or + MMR.")
    parser.add_argument("--top-k", type=int, default=None,
                        help="Retrieval cutoff k (default settings.top_k_final).")
    args = parser.parse_args()

    if args.retrieval_only and args.generation_only:
        parser.error("--retrieval-only and --generation-only are mutually exclusive.")
    mode = "both"
    if args.retrieval_only:
        mode = "retrieval"
    elif args.generation_only:
        mode = "generation"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    print("AyurKosha — Evaluation Suite")
    print("=" * 50)
    print(f"Mode: {mode}  |  Pipeline: {args.pipeline}  |  Judge: {args.judge}  |  HyDE: {args.hyde}")
    print("=" * 50)

    payload = run_eval(
        dataset_path=args.dataset,
        output_dir=args.output,
        mode=mode,
        judge=args.judge,
        k=args.top_k,
        use_hyde=args.hyde,
        embed_cache=not args.no_embed_cache,
        pipeline=args.pipeline,
    )

    print("\nSUMMARY")
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    print(f"\nSaved to: {payload['saved_to']}")

    skips = payload["summary"]["rerank_skips"]
    print(f"Rerank skips: {skips}/{payload['summary']['n_questions']}  |  Status: {payload['status']}")
    if payload["status"] == "INVALID" and not args.allow_rerank_skips:
        print("Run INVALID: some questions were scored on unranked results. "
              "Re-run, or pass --allow-rerank-skips to accept.", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
