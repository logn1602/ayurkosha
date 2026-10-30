"""
AyurKosha — Retrieval Traces
Persists what every eval run retrieved, so it can be rescored later against
any label file with zero API calls, and without the index or stores it ran on.

Each run writes a JSONL file next to its JSON results:

  line 1    {"type": "run", ...}       config, index, text flags, retrieval
                                       params, labels file + sha256, timestamp,
                                       status and the run's own summary
  line 2..  {"type": "question", ...}  id, question, config, the gold sources
                                       used, and the ranked candidates at each
                                       stage: "fused" (RRF), "rerank", "mmr"
                                       (whichever ran), plus which stage, and
                                       how many of it, the metrics scored

Each candidate keeps chunk_id, work (canonical title), source file, text_name,
page and the stage score (rrf_score for fused; rerank_score for rerank, and
for mmr, whose relevance term is the rerank score). Fused candidates also
record which retrievers found them.

``rescore`` reuses the eval's own scoring and averaging
(retrieval_metrics.score_retrieval + aggregate), so with the original labels
it reproduces the run's summary exactly.

Build this in: Phase 6
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from config.settings import settings
from src.evaluation import retrieval_metrics
from src.evaluation.aggregate import aggregate

STAGE_SCORE_KEYS = {"fused": "rrf_score", "rerank": "rerank_score", "mmr": "rerank_score"}
TEXT_FLAGS = ("apply_font_char_map", "bm25_fold_diacritics", "split_glued_ocr_words", "contextual_chunk_headers",
              "exclude_charaka", "exclude_ah_srikantha_murthy", "exclude_ah_sanskrit_commentaries")
RETRIEVAL_PARAMS = ("semantic_retrieve_n", "bm25_retrieve_n", "rrf_k", "rerank_first_pass_n", "top_k_final")


def labels_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def candidate(chunk: dict[str, Any], stage: str) -> dict[str, Any]:
    """Serializable record of one ranked candidate at one stage."""
    meta = chunk.get("metadata") or {}
    out = {
        "chunk_id": chunk.get("chunk_id"),
        "parent_id": chunk.get("parent_id") or meta.get("parent_id"),
        "work": retrieval_metrics.chunk_work_key(chunk),
        "source": meta.get("source"),
        "text_name": meta.get("text_name"),
        "page": meta.get("page"),
        "score": chunk.get(STAGE_SCORE_KEYS[stage]),
    }
    if stage == "fused":
        out["retrievers"] = chunk.get("retrievers")
    return out


def question_trace(item: dict[str, Any], config_name: str, retrieved: dict[str, Any]) -> dict[str, Any]:
    stages = retrieved.get("stages") or {}
    return {
        "type": "question",
        "id": item.get("id"),
        "question": item.get("question"),
        "gold_sources": item.get("gold_sources", []),
        "config": config_name,
        "scored_stage": retrieved.get("scored_stage"),
        "scored_n": len(retrieved.get("scored") or []),
        "rerank_skipped": retrieved.get("rerank_skipped", False),
        "hyde_passage": retrieved.get("hyde_passage"),
        "stages": {name: [candidate(c, name) for c in chunks] for name, chunks in stages.items()},
    }


def run_metadata(config: dict[str, Any], dataset_path: str | Path, n_questions: int,
                 status: str, summary: dict[str, Any]) -> dict[str, Any]:
    from src.utils.transliterate import ENGLISH_TOP_N

    return {
        "type": "run",
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "config": config,
        "index": settings.pinecone_index_name,
        "text_flags": {**{f: getattr(settings, f) for f in TEXT_FLAGS},
                       "romanization_english_top_n": ENGLISH_TOP_N},
        "retrieval_params": {p: getattr(settings, p) for p in RETRIEVAL_PARAMS},
        "labels_file": str(dataset_path),
        "labels_sha256": labels_sha256(dataset_path),
        "n_questions": n_questions,
        "status": status,
        "summary": summary,
    }


def write_trace(path: str | Path, meta: dict[str, Any], traces: list[dict[str, Any]]) -> Path:
    path = Path(path)
    with open(path, "w", encoding="utf-8") as f:
        for line in [meta, *traces]:
            f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return path


def read_trace(path: str | Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """(run metadata, question traces) from a trace JSONL file."""
    with open(path, encoding="utf-8") as f:
        lines = [json.loads(line) for line in f if line.strip()]
    if not lines or lines[0].get("type") != "run":
        raise ValueError(f"{path} is not a retrieval trace (missing run header).")
    return lines[0], [line for line in lines[1:] if line.get("type") == "question"]


def load_labels(path: str | Path) -> dict[str, list[str]]:
    """{question id: gold_sources} from an eval dataset file."""
    with open(path, encoding="utf-8") as f:
        return {item["id"]: item.get("gold_sources", []) for item in json.load(f)}


def load_supporting(path: str | Path) -> dict[str, list[str]]:
    """{question id: supporting parent chunk ids} (provenance) from an eval dataset file."""
    with open(path, encoding="utf-8") as f:
        return {item["id"]: (item.get("provenance") or {}).get("supporting_chunk_ids") or []
                for item in json.load(f)}


def scored_chunks(trace: dict[str, Any]) -> list[dict[str, Any]]:
    """The exact ranked list the run's metrics were computed on, as chunk-like dicts."""
    stage = trace.get("scored_stage")
    cands = (trace.get("stages") or {}).get(stage, [])[: trace.get("scored_n", 0)]
    return [{"chunk_id": c["chunk_id"], "parent_id": c.get("parent_id"),
             "metadata": {"text_name": c.get("text_name"), "source": c.get("source"), "page": c.get("page")}}
            for c in cands]


def first_gold_rank(trace: dict[str, Any], gold_sources: list[str]) -> int | None:
    """1-based rank of the first gold-work chunk in the scored list, or None."""
    relevant = retrieval_metrics.relevant_keys(gold_sources)
    for rank, chunk in enumerate(scored_chunks(trace), start=1):
        if retrieval_metrics.chunk_work_key(chunk) in relevant:
            return rank
    return None


def first_passage_rank(trace: dict[str, Any], supporting_ids: list[str]) -> int | None:
    """1-based rank of the first scored chunk hitting a supporting passage, or None."""
    return retrieval_metrics.first_passage_rank(scored_chunks(trace), supporting_ids)


def rescore(meta: dict[str, Any], traces: list[dict[str, Any]], labels: dict[str, list[str]],
            k: int | None = None, supporting: dict[str, list[str]] | None = None) -> dict[str, Any]:
    """Recompute retrieval metrics for a saved run against ``labels``.

    With ``supporting`` ({id: supporting parent ids}), also passage-level
    metrics. Questions missing from ``labels`` are skipped (and listed).
    Returns {"summary", "per_question", "missing"}.
    """
    k = k or meta["config"]["k"]
    records, per_question, missing = [], {}, []
    for t in traces:
        if t["id"] not in labels:
            missing.append(t["id"])
            continue
        gold, chunks = labels[t["id"]], scored_chunks(t)
        metrics = retrieval_metrics.score_retrieval(chunks, gold, k)
        record = {"id": t["id"], "rerank_skipped": t.get("rerank_skipped", False), "retrieval": metrics}
        per_question[t["id"]] = {**metrics, "first_gold_rank": first_gold_rank(t, gold)}
        passage = retrieval_metrics.score_passages(chunks, (supporting or {}).get(t["id"]) or [], k)
        if passage is not None:
            record["passage"] = passage
            per_question[t["id"]]["passage"] = {
                **passage, "first_rank": first_passage_rank(t, supporting[t["id"]])}
        records.append(record)
    return {"summary": aggregate(records), "per_question": per_question, "missing": missing}


# ── summary table ─────────────────────────────────────────────────────

# Pipelines whose scored list is only k deep, so full-list MRR = MRR@k there.
FULL_LIST_MRR_NA = frozenset({"rerank_mmr"})


def _fmt(vals: list[float]) -> str:
    if not vals:
        return "n/a"
    if len(vals) == 1:
        return f"{vals[0]:.3f}"
    return f"{sum(vals) / len(vals):.3f} ({min(vals):.3f}–{max(vals):.3f})"


def summary_table(groups: list[tuple[str, list[tuple[dict[str, Any], dict[str, Any]]]]]) -> list[str]:
    """Markdown table of Hit@k, Recall@k, MRR@k (headline) and full-list MRR@n per config.

    ``groups`` is [(label, [(run metadata, summary), ...])]; repeated runs show
    as mean (min–max). MRR@n is n/a for rerank_mmr, whose scored list is k deep.
    """
    metas = [meta for _, runs in groups for meta, _ in runs]
    k = metas[0]["config"]["k"] if metas else settings.top_k_final
    n = ((metas[0].get("retrieval_params") or {}).get("rerank_first_pass_n") if metas else None) \
        or settings.rerank_first_pass_n
    lines = [f"| config | Hit@{k} work | Recall@{k} work | MRR@{k} work | Hit@{k} passage | "
             f"Recall@{k} passage | MRR@{k} passage | MRR@{n} work |", "|---|---|---|---|---|---|---|---|"]
    for label, runs in groups:
        def vals(section, key):
            return [s[section][key] for _, s in runs
                    if isinstance((s.get(section) or {}).get(key), (int, float))]
        full = ("n/a" if any(m["config"]["pipeline"] in FULL_LIST_MRR_NA for m, _ in runs)
                else _fmt(vals("retrieval", "mrr")))
        lines.append(f"| {label} | {_fmt(vals('retrieval', 'hit_rate'))} | {_fmt(vals('retrieval', 'recall_at_k'))} | "
                     f"{_fmt(vals('retrieval', 'mrr_at_k'))} | {_fmt(vals('passage', 'hit_rate'))} | "
                     f"{_fmt(vals('passage', 'recall_at_k'))} | {_fmt(vals('passage', 'mrr_at_k'))} | {full} |")
    lines.append(f"\n**Work level** (lenient bound): any chunk of a gold work counts. **Passage level** (strict "
                 f"bound): a chunk counts only if its parent is a supporting passage, or it is within "
                 f"±{retrieval_metrics.PASSAGE_PAGE_WINDOW} page of one in the same source file; passage "
                 f"Recall@{k} is the share of supporting passages covered, capped at {k}/(set size) for large "
                 f"sets. MRR@{k} is the headline MRR at both levels (first hit within the top {k}). "
                 f"MRR@{n} uses the whole {n}-deep scored list; n/a for rerank_mmr, whose list is only {k} long.")
    return lines


# ── per-question breakdown ────────────────────────────────────────────

def _rank_cell(ranks: list[int | None]) -> str:
    return "/".join(str(r) if r else "-" for r in ranks)


def _compare_cell(base: int | None, other: int | None) -> str:
    """'+' other ranks gold higher (better), '-' lower, '=' same, '.' neither finds it."""
    if base is None and other is None:
        return "."
    if base is None:
        return "+"
    if other is None:
        return "-"
    return "+" if other < base else "-" if other > base else "="


def per_question_table(columns: list[tuple[str, list[list[dict[str, Any]]]]], labels: dict[str, list[str]],
                       comparisons: tuple[tuple[str, str], ...] = (),
                       supporting: dict[str, list[str]] | None = None) -> list[str]:
    """Markdown table: rank of the first gold hit per question, per column.

    Work level by default; with ``supporting`` ({id: supporting parent ids}),
    passage level instead (rank of the first chunk hitting a supporting
    passage). ``columns`` is [(label, [question traces of run 1, run 2, ...])];
    repeated runs (HyDE) show as r1/r2/r3. ``comparisons`` [(base, other)] add
    a column marking where ``other`` ranks the hit better (+) or worse (-)
    than ``base`` (single-run columns only).
    """
    def rank_of(t):
        if supporting is not None:
            return first_passage_rank(t, supporting.get(t["id"]) or [])
        return first_gold_rank(t, labels[t["id"]])

    def gold_cell(qid):
        if supporting is not None:
            return f"{len(supporting.get(qid) or [])} passages"
        return ", ".join(labels[qid])

    ranks: dict[str, dict[str, list[int | None]]] = {}
    for label, runs in columns:
        for run in runs:
            for t in run:
                if t["id"] in labels:
                    ranks.setdefault(t["id"], {}).setdefault(label, []).append(rank_of(t))
    head = ["id", "gold"] + [label for label, _ in columns] + [f"{o} vs {b}" for b, o in comparisons]
    lines = ["| " + " | ".join(head) + " |", "|" + "---|" * len(head)]
    tally = {c: {"+": 0, "-": 0, "=": 0, ".": 0} for c in comparisons}
    for qid in sorted(ranks):
        row = [qid, gold_cell(qid)] + [_rank_cell(ranks[qid].get(label, [])) for label, _ in columns]
        for c in comparisons:
            base, other = (ranks[qid].get(x, [None])[0] for x in c)
            mark = _compare_cell(base, other)
            tally[c][mark] += 1
            row.append(mark)
        lines.append("| " + " | ".join(row) + " |")
    for (b, o), t in tally.items():
        lines.append(f"\n{o} vs {b}: better {t['+']}, worse {t['-']}, same {t['=']}, neither finds gold {t['.']}")
    what = ("chunk hitting a supporting passage (parent id, or ±1 page in the same file)"
            if supporting is not None else "gold-work chunk")
    lines.append(f"\nCells: rank of the first {what} in the scored list (1 = top; '-' = not in it). "
                 "Hit@k and MRR@k count only ranks <= k; the full-list MRR counts every rank.")
    return lines
