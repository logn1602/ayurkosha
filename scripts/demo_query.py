"""
AyurKosha — Live Demo Query (screenshot-friendly)
Runs the full RAG pipeline on one question and prints a clean, formatted
answer with verified citations. Designed to look good in a terminal
screenshot for a README / portfolio.

Costs a few cents of Anthropic credit per run (query expansion + generation).
For a zero-cost version that stops before generation, use
scripts/dry_run_query.py instead.

Run:  python scripts/demo_query.py
      python scripts/demo_query.py --question "What are the ingredients of Dashamoola Kashayam?"
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# 【N】 citation markers -> force UTF-8 on the Windows console (cp1252).
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

# Quiet the pipeline's INFO logs so the screenshot shows only the result.
logging.basicConfig(level=logging.WARNING)

from api.dependencies import get_parent_store
from api.routes.query import run_query_pipeline
from api.schemas import QueryRequest

BAR = "=" * 68
RULE = "-" * 68
DEFAULT_QUESTION = "What is the Ayurvedic treatment for Amavata?"


def main():
    parser = argparse.ArgumentParser(description="Run a live AyurKosha demo query.")
    parser.add_argument("--question", default=DEFAULT_QUESTION)
    parser.add_argument("--top-k", type=int, default=6)
    args = parser.parse_args()

    print(BAR)
    print("  AyurKosha — Ayurvedic Knowledge RAG (hybrid search + verified citations)")
    print(BAR)
    print(f"Question: {args.question}\n")
    print("Pipeline: query expansion → semantic + BM25 → RRF fusion →")
    print("          Cohere rerank → MMR → context → Claude → citation verify\n")

    req = QueryRequest(question=args.question, top_k=args.top_k)
    resp = run_query_pipeline(req, get_parent_store())

    print(f"Query expansion produced {len(resp.query_variants)} search variants:")
    for v in resp.query_variants:
        print(f"  • {v}")

    print("\n" + RULE)
    print("ANSWER")
    print(RULE)
    print(resp.answer)

    print("\n" + RULE)
    print("SOURCES")
    print(RULE)
    for s in resp.sources:
        page = f"p.{s.page}" if s.page is not None else "p.—"
        print(f"  【{s.citation_number}】 {s.document} ({page})")

    print("\n" + BAR)
    verified = len(resp.sources)
    hallucinated = len(resp.hallucinated_citations)
    print(f"  ✓ {verified} sources cited · {hallucinated} hallucinated citations "
          f"· {len(resp.query_variants)} query variants")
    print(BAR)


if __name__ == "__main__":
    main()
