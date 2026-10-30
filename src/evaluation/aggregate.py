"""
AyurKosha — Eval Result Aggregation
Averages per-question metric records into a run summary. Shared by the eval
runner and offline rescoring (src/evaluation/traces.py), so a rescored run
reproduces the original summary exactly.

Build this in: Phase 6
"""

from __future__ import annotations

from typing import Any


def aggregate(results: list[dict[str, Any]]) -> dict[str, Any]:
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
            "mrr_at_k": _avg("retrieval", "mrr_at_k"),
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
