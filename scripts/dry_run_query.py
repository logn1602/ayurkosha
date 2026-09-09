"""
AyurKosha — Query Pipeline Dry Run (no Anthropic cost)
Runs the retrieval + context-assembly half of the /query pipeline and prints
the exact context block that WOULD be sent to Claude — without making any
Anthropic (paid) call. Use this to verify everything up to generation works
before spending credits on a live /query.

What runs (and what it costs):
  - Query expansion / filter inference  -> SKIPPED (these are Anthropic calls).
    The raw question is used as the single retrieval variant, unfiltered.
  - Semantic + BM25 retrieval, RRF, Cohere rerank, MMR  -> Cohere + Pinecone
    only (no Anthropic). Cohere trial usage is negligible for one query.
  - Parent expansion, reorder, context builder  -> pure local code, $0.
  - Claude generation  -> SKIPPED. The assembled context is printed instead.

Run:  python scripts/dry_run_query.py
      python scripts/dry_run_query.py --question "What is the dose of Triphala Churna?"
      python scripts/dry_run_query.py --top-k 8
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is importable when run directly.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The context block contains 【】 citation markers; force UTF-8 so the Windows
# console (cp1252 by default) doesn't choke on them.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover — non-reconfigurable stream
    pass

from src.context.builder import build_context
from src.context.parent_expand import expand_to_parents
from src.context.reorder import reorder_chunks
from src.ingestion.parent_store import load_parent_store
from src.reranking.cohere_rerank import rerank
from src.reranking.mmr import mmr_rerank
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.keyword import keyword_search
from src.retrieval.semantic import semantic_search

DEFAULT_QUESTION = "What is the Ayurvedic treatment for Amavata?"


def main():
    parser = argparse.ArgumentParser(
        description="Dry-run the AyurKosha query pipeline (no Anthropic cost)."
    )
    parser.add_argument("--question", default=DEFAULT_QUESTION,
                        help="The question to run through retrieval + context assembly.")
    parser.add_argument("--top-k", type=int, default=6,
                        help="Final number of context passages (default 6).")
    parser.add_argument("--doc-type", default=None,
                        help="Optional doc_type filter (e.g. classical_text). "
                             "Filter inference is skipped in the dry run.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    question = args.question
    print("AyurKosha — Query Pipeline DRY RUN (no Anthropic call)")
    print("=" * 60)
    print(f"Question: {question}")
    if args.doc_type:
        print(f"doc_type filter: {args.doc_type}")
    print("=" * 60)

    # Query expansion + filter inference are Anthropic calls — skipped here.
    # Use the raw question as the single retrieval variant.
    variants = [question]

    semantic_results = semantic_search(variants, doc_type_filter=args.doc_type)
    keyword_results = keyword_search(variants)
    print(f"[retrieval] semantic={len(semantic_results)}  bm25={len(keyword_results)}")

    fused = reciprocal_rank_fusion([semantic_results, keyword_results])
    print(f"[fusion]    {len(fused)} unique chunks")

    reranked = rerank(question, fused)
    print(f"[rerank]    {len(reranked)} after Cohere rerank")

    diverse = mmr_rerank(question, reranked, top_k=args.top_k)
    print(f"[mmr]       {len(diverse)} diverse passages")

    parent_store = load_parent_store()
    expanded = expand_to_parents(diverse, parent_store)
    ordered = reorder_chunks(expanded)
    print(f"[context]   {len(ordered)} passages after parent-expand + reorder")

    context_block, sources = build_context(ordered)

    if not sources:
        print("\n⚠️  No sources retrieved. Check that ingestion has been run "
              "(Pinecone index + data/cache/*).")
        return

    print("\n" + "=" * 60)
    print("SOURCES (what the answer would cite)")
    print("=" * 60)
    for s in sources:
        page = f"p.{s['page']}" if s.get("page") is not None else "p.—"
        heading = s.get("heading") or "—"
        print(f"  【{s['citation_number']}】 {s['document']} ({page}) — {heading}")

    print("\n" + "=" * 60)
    print("CONTEXT BLOCK (this is exactly what would be sent to Claude)")
    print("=" * 60)
    print(context_block)
    print("=" * 60)
    print(f"\n✅ Dry run complete. {len(sources)} passages assembled, $0 Anthropic spend.")
    print("   If these passages look relevant, the pipeline works end-to-end up")
    print("   to generation — the only remaining step is the paid Claude call.")


if __name__ == "__main__":
    main()
