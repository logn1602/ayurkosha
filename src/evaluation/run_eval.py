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

Which ranked list retrieval metrics score is set by ``pipeline``:
  - "rrf"        : RRF-fused semantic + BM25, top rerank_first_pass_n (no rerank)
  - "rerank"     : Cohere-reranked top rerank_first_pass_n (default — the
                   historical eval definition)
  - "rerank_mmr" : the final top-k after MMR (what generation actually sees)
MMR only runs when it is scored or when generation needs context, so
retrieval-only "rrf"/"rerank" runs spend no MMR embed calls.

Every run also writes a retrieval trace (src/evaluation/traces.py): a JSONL
beside the JSON results, with the ranked candidates at each stage per
question, so the run can be rescored later against any label file
(scripts/rescore.py) without the index or stores it ran on.

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
from src.evaluation import generation_metrics, retrieval_metrics, traces
from src.evaluation.aggregate import aggregate
from src.ingestion import embedder
from src.ingestion.parent_store import load_parent_store
from src.reranking.cohere_rerank import rerank_with_retry
from src.reranking.mmr import mmr_rerank
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.keyword import keyword_search
from src.query.hyde import generate_hypothetical_document
from src.retrieval.semantic import semantic_search

logger = logging.getLogger(__name__)

PIPELINES = ("rrf", "rerank", "rerank_mmr")

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


def _retrieve(
    question: str,
    k: int,
    parent_store,
    use_hyde: bool = False,
    pipeline: str = "rerank",
    need_context: bool = True,
) -> dict[str, Any]:
    """Run retrieval for one question; return the scored list + generation context.

    Skips query expansion / filter inference (no Anthropic) — uses the raw
    question as the single variant, mirroring scripts/dry_run_query.py.
    With ``use_hyde``, also searches a HyDE passage (one cheap Claude call).
    ``pipeline`` picks the ranked list returned as ``scored`` (see module
    docstring); context is only assembled when ``need_context``.
    """
    variants = [question]
    hyde_passage = generate_hypothetical_document(question) if use_hyde else None
    semantic_results = semantic_search(
        variants, hyde_passages=[hyde_passage] if hyde_passage else None
    )
    keyword_results = keyword_search(variants)
    fused = reciprocal_rank_fusion([semantic_results, keyword_results])
    if pipeline == "rrf":
        ranked, rerank_skipped = fused[:settings.rerank_first_pass_n], False
    else:
        ranked, rerank_skipped = rerank_with_retry(question, fused)

    diverse = None
    if pipeline == "rerank_mmr" or need_context:
        diverse = mmr_rerank(question, ranked, top_k=k)
    scored = diverse if pipeline == "rerank_mmr" else ranked
    stages = {"fused": fused}
    if pipeline != "rrf":
        stages["rerank"] = ranked
    if diverse is not None:
        stages["mmr"] = diverse
    scored_stage = {"rrf": "fused", "rerank": "rerank", "rerank_mmr": "mmr"}[pipeline]

    context_block, sources, ordered = "", [], []
    if need_context:
        ordered = reorder_chunks(expand_to_parents(diverse, parent_store))
        context_block, sources = build_context(ordered)
    return {
        "scored": scored,          # ranked list for recall/precision/mrr
        "scored_stage": scored_stage,
        "stages": stages,          # every ranked list, for the retrieval trace
        "hyde_passage": hyde_passage,
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
    pipeline: str = "rerank",
    config_name: str = "rerank",
) -> dict[str, Any]:
    """Evaluate one dataset item and return its per-question result record.

    The record carries the retrieval trace under ``_trace``; run_eval moves it
    to the trace file.
    """
    question = item["question"]
    gold_sources = item.get("gold_sources", [])
    gold_answer = item.get("gold_answer", "")

    retrieved = _retrieve(question, k, parent_store, use_hyde=use_hyde, pipeline=pipeline,
                          need_context=mode in ("generation", "both"))
    record: dict[str, Any] = {
        "id": item.get("id"),
        "question": question,
        "category": item.get("category"),
        "difficulty": item.get("difficulty"),
        "rerank_skipped": retrieved["rerank_skipped"],
        "_trace": traces.question_trace(item, config_name, retrieved),
    }

    if mode in ("retrieval", "both"):
        record["retrieval"] = retrieval_metrics.score_retrieval(
            retrieved["scored"], gold_sources, k
        )
        passage = retrieval_metrics.score_passages(
            retrieved["scored"], (item.get("provenance") or {}).get("supporting_chunk_ids") or [], k)
        if passage is not None:
            record["passage"] = passage

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


def _results_path(output_dir: str | Path, config_name: str) -> Path:
    """Unused timestamped path ``eval_<stamp>_<config>.json`` in ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"eval_{datetime.now():%Y%m%d_%H%M%S}_{config_name}"
    path, n = output_dir / f"{stem}.json", 2
    while path.exists() or path.with_suffix(".jsonl").exists():
        path, n = output_dir / f"{stem}_{n}.json", n + 1
    return path


def _save_results(payload: dict[str, Any], path: Path) -> Path:
    """Write the results payload to ``path``."""
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
    pipeline: str = "rerank",
    config_name: str | None = None,
) -> dict[str, Any]:
    """Run the evaluation suite and save timestamped results + retrieval trace.

    ``config_name`` labels the run in file names and traces (default: the
    pipeline, plus "+hyde").

    With ``embed_cache`` (default), Cohere embeddings are served from / saved
    to data/cache/embedding_cache.json, so reruns over the same questions
    don't spend embed calls (HyDE passages differ per run and still miss).

    A run where any question fell back to unranked results (rerank skipped
    after all retries) is marked ``"status": "INVALID"`` — its retrieval
    metrics don't reflect the real pipeline.

    Returns the summary payload (also written to ``output_dir``).
    """
    if pipeline not in PIPELINES:
        raise ValueError(f"pipeline must be one of {PIPELINES}, got {pipeline!r}")
    k = k or settings.top_k_final
    config_name = config_name or pipeline + ("+hyde" if use_hyde else "")
    dataset = load_dataset(dataset_path)
    parent_store = load_parent_store()

    logger.info("Evaluating %d questions (mode=%s, pipeline=%s, k=%d, judge=%s, hyde=%s).",
                len(dataset), mode, pipeline, k, judge, use_hyde)
    if embed_cache:
        embedder.enable_embedding_cache()
    try:
        results = [evaluate_item(item, k, mode, judge, parent_store,
                                 use_hyde=use_hyde, pipeline=pipeline, config_name=config_name)
                   for item in dataset]
    finally:
        # Save even on a crash (e.g. quota exhausted) so finished work is kept.
        if embed_cache:
            embedder.save_embedding_cache()
            embedder.disable_embedding_cache()

    question_traces = [r.pop("_trace") for r in results]
    summary = aggregate(results)
    if summary["rerank_skips"]:
        logger.warning("%d/%d question(s) skipped rerank after retries — run is INVALID.",
                       summary["rerank_skips"], len(results))
    status = "INVALID" if summary["rerank_skips"] else "VALID"
    config = {"name": config_name, "pipeline": pipeline, "use_hyde": use_hyde, "mode": mode, "k": k, "judge": judge}
    payload = {
        "status": status,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config_name": config_name,
        "mode": mode,
        "pipeline": pipeline,
        "k": k,
        "judge": judge,
        "hyde": use_hyde,
        "summary": summary,
        "results": results,
    }
    path = _results_path(output_dir, config_name)
    trace_path = traces.write_trace(
        path.with_suffix(".jsonl"),
        traces.run_metadata(config, dataset_path, len(dataset), status, summary),
        question_traces)
    payload["trace_file"] = str(trace_path)
    saved = _save_results(payload, path)
    logger.info("Saved eval results to %s (trace %s)", saved, trace_path.name)
    payload["saved_to"] = str(saved)
    return payload
