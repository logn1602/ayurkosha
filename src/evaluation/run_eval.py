"""
AyurKosha — Evaluation Suite Runner
Runs the eval dataset through the pipeline and saves timestamped results.

Three modes:
  - "retrieval"  : retrieval metrics only. No Anthropic calls — runs for free
                   even with a zero credit balance.
  - "generation" : generation metrics only (still retrieves to build context,
                   then calls Claude to generate — needs Anthropic credits).
  - "both"       : retrieval + generation metrics.

Retrieval for eval uses the raw question as the single variant (query
expansion / filter inference are skipped) so the measured retrieval quality
is reproducible and doesn't depend on paid calls. The optional LLM judge
(--judge) adds Claude-scored faithfulness/relevance/completeness.

Build this in: Phase 6
"""

from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from src.context.builder import build_context
from src.context.parent_expand import expand_to_parents
from src.context.reorder import reorder_chunks
from src.evaluation import generation_metrics, retrieval_metrics
from src.ingestion import embedder
from src.ingestion.parent_store import load_parent_store
from src.reranking.cohere_rerank import rerank_with_retry
from src.reranking.mmr import mmr_rerank
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.keyword import keyword_search
from src.query.hyde import generate_hypothetical_document
from src.retrieval.semantic import semantic_search

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DATASET = PROJECT_ROOT / "data" / "eval" / "eval_dataset.json"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "eval" / "eval_results"


def load_dataset(path: str | Path = DEFAULT_DATASET) -> list[dict[str, Any]]:
    """Load the eval dataset (a JSON list of question dicts)."""
    path = Path(path)
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"Eval dataset at {path} must be a JSON list.")
    return data


def _retrieve(question: str, k: int, parent_store, use_hyde: bool = False) -> dict[str, Any]:
    """Run retrieval for one question; return ranked list + generation context.

    Skips query expansion / filter inference (no Anthropic) — uses the raw
    question as the single variant, mirroring scripts/dry_run_query.py.
    With ``use_hyde``, also searches a HyDE passage (one cheap Claude call).
    """
    variants = [question]
    hyde_passage = generate_hypothetical_document(question) if use_hyde else None
    semantic_results = semantic_search(
        variants, hyde_passages=[hyde_passage] if hyde_passage else None
    )
    keyword_results = keyword_search(variants)
    fused = reciprocal_rank_fusion([semantic_results, keyword_results])
    reranked, rerank_skipped = rerank_with_retry(question, fused)
    diverse = mmr_rerank(question, reranked, top_k=k)
    expanded = expand_to_parents(diverse, parent_store)
    ordered = reorder_chunks(expanded)
    context_block, sources = build_context(ordered)
    return {
        "reranked": reranked,      # ranked list for recall/precision/mrr
        "rerank_skipped": rerank_skipped,
        "context_block": context_block,
        "sources": sources,
        "final_passages": ordered,
    }


def evaluate_item(
    item: dict[str, Any],
    k: int,
    mode: str,
    judge: bool,
    parent_store,
    use_hyde: bool = False,
) -> dict[str, Any]:
    """Evaluate one dataset item and return its per-question result record."""
    question = item["question"]
    gold_sources = item.get("gold_sources", [])
    gold_answer = item.get("gold_answer", "")

    retrieved = _retrieve(question, k, parent_store, use_hyde=use_hyde)
    record: dict[str, Any] = {
        "id": item.get("id"),
        "question": question,
        "category": item.get("category"),
        "difficulty": item.get("difficulty"),
        "rerank_skipped": retrieved["rerank_skipped"],
    }

    if mode in ("retrieval", "both"):
        record["retrieval"] = retrieval_metrics.score_retrieval(
            retrieved["reranked"], gold_sources, k
        )

    if mode in ("generation", "both"):
        from src.generation.generator import generate_answer
        from src.generation.citation_verify import verify_citations

        try:
            raw_answer = generate_answer(question, retrieved["context_block"])
            verified = verify_citations(raw_answer, retrieved["sources"])
            answer = verified["answer"]
            gen = generation_metrics.score_generation(
                answer, question, retrieved["context_block"], retrieved["sources"]
            )
            gen["ok"] = True
            record["answer"] = answer
        except Exception as exc:  # noqa: BLE001 — e.g. exhausted credits
            logger.warning("Generation failed for %s (%s).", item.get("id"), exc)
            gen = {"ok": False, "error": str(exc)}
        record["generation"] = gen

        if judge and gen.get("ok"):
            from src.evaluation.llm_judge import judge_answer
            record["judge"] = judge_answer(question, record["answer"], gold_answer)

    return record


def _aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Average the numeric metrics across all per-question records."""
    def _avg(section: str, field: str) -> float | None:
        vals = [r[section][field] for r in results
                if section in r and isinstance(r[section].get(field), (int, float))]
        return round(sum(vals) / len(vals), 4) if vals else None

    summary: dict[str, Any] = {
        "n_questions": len(results),
        "rerank_skips": sum(1 for r in results if r.get("rerank_skipped")),
    }
    if any("retrieval" in r for r in results):
        summary["retrieval"] = {
            "recall_at_k": _avg("retrieval", "recall_at_k"),
            "precision_at_k": _avg("retrieval", "precision_at_k"),
            "mrr": _avg("retrieval", "mrr"),
            "hit_rate": _avg("retrieval", "hit"),
        }
    if any("generation" in r for r in results):
        ok = [r for r in results if r.get("generation", {}).get("ok")]
        summary["generation"] = {
            "answered": len(ok),
            "citation_accuracy": _avg_over(ok, "generation", "citation_accuracy"),
            "grounding_proxy": _avg_over(ok, "generation", "grounding_proxy"),
            "relevance_proxy": _avg_over(ok, "generation", "relevance_proxy"),
            "safety_disclaimer_rate": _rate(ok, "generation", "has_safety_disclaimer"),
        }
    if any("judge" in r for r in results):
        judged = [r for r in results if r.get("judge", {}).get("ok")]
        summary["judge"] = {
            "scored": len(judged),
            "faithfulness": _avg_over(judged, "judge", "faithfulness"),
            "relevance": _avg_over(judged, "judge", "relevance"),
            "completeness": _avg_over(judged, "judge", "completeness"),
        }
    return summary


def _avg_over(records, section: str, field: str) -> float | None:
    vals = [r[section][field] for r in records
            if isinstance(r.get(section, {}).get(field), (int, float))]
    return round(sum(vals) / len(vals), 4) if vals else None


def _rate(records, section: str, field: str) -> float | None:
    vals = [bool(r[section][field]) for r in records if field in r.get(section, {})]
    return round(sum(vals) / len(vals), 4) if vals else None


def _save_results(payload: dict[str, Any], output_dir: str | Path) -> Path:
    """Write the results payload to a timestamped JSON file."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = output_dir / f"eval_{stamp}.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return path


def run_eval(
    dataset_path: str | Path = DEFAULT_DATASET,
    output_dir: str | Path = DEFAULT_OUTPUT_DIR,
    mode: str = "both",
    judge: bool = False,
    k: int | None = None,
    use_hyde: bool = False,
    embed_cache: bool = True,
) -> dict[str, Any]:
    """Run the evaluation suite and save timestamped results.

    With ``embed_cache`` (default), Cohere embeddings are served from / saved
    to data/cache/embedding_cache.json, so reruns over the same questions
    don't spend embed calls (HyDE passages differ per run and still miss).

    A run where any question fell back to unranked results (rerank skipped
    after all retries) is marked ``"status": "INVALID"`` — its retrieval
    metrics don't reflect the real pipeline.

    Returns the summary payload (also written to ``output_dir``).
    """
    k = k or settings.top_k_final
    dataset = load_dataset(dataset_path)
    parent_store = load_parent_store()

    logger.info("Evaluating %d questions (mode=%s, k=%d, judge=%s, hyde=%s).",
                len(dataset), mode, k, judge, use_hyde)
    if embed_cache:
        embedder.enable_embedding_cache()
    try:
        results = [evaluate_item(item, k, mode, judge, parent_store, use_hyde=use_hyde)
                   for item in dataset]
    finally:
        # Save even on a crash (e.g. quota exhausted) so finished work is kept.
        if embed_cache:
            embedder.save_embedding_cache()
            embedder.disable_embedding_cache()

    summary = _aggregate(results)
    if summary["rerank_skips"]:
        logger.warning("%d/%d question(s) skipped rerank after retries — run is INVALID.",
                       summary["rerank_skips"], len(results))
    payload = {
        "status": "INVALID" if summary["rerank_skips"] else "VALID",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": mode,
        "k": k,
        "judge": judge,
        "hyde": use_hyde,
        "summary": summary,
        "results": results,
    }
    saved = _save_results(payload, output_dir)
    logger.info("Saved eval results to %s", saved)
    payload["saved_to"] = str(saved)
    return payload
