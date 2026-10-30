"""Tests for retrieval traces, offline rescoring and the per-question breakdown.

The retrieval stack is faked (no Cohere / Pinecone / Claude), so a "run" is
deterministic and its trace can be checked end to end.

Run: python -m pytest tests/test_traces.py
"""

import importlib.util
import json
from pathlib import Path

import pytest

from src.evaluation import run_eval as re_mod
from src.evaluation import traces
from src.evaluation.traces import (labels_sha256, load_labels, per_question_table, read_trace, rescore,
                                   summary_table)

ROOT = Path(__file__).resolve().parents[1]


def _chunk(cid, source, page, score):
    return {"chunk_id": cid, "score": score, "text": f"text of {cid}", "parent_id": f"{cid}_P",
            "metadata": {"source": source, "text_name": None, "page": page}}


SEMANTIC = [_chunk("api_1", "api_all_volume.pdf", 40, 0.9), _chunk("afi_1", "afi_part1.pdf", 112, 0.8),
            _chunk("ss_1", "sushruta_samhita_vol_2.pdf", 371, 0.7)]
KEYWORD = [_chunk("ss_1", "sushruta_samhita_vol_2.pdf", 371, 12.0), _chunk("afi_2", "afi_part1.pdf", 113, 9.0),
           _chunk("api_2", "api_all_volume.pdf", 41, 5.0)]
DATASET = [
    {"id": "q1", "question": "properties of Asvagandha?", "gold_sources": ["api"]},
    {"id": "q2", "question": "four modalities for Arsha?", "gold_sources": ["sushruta"]},
    {"id": "q3", "question": "what is Dinacarya?", "gold_sources": ["ashtanga_hridaya"]},   # never retrieved
]


@pytest.fixture
def fake_stack(monkeypatch, tmp_path):
    # Real retrievers tag their results; fusion turns the tags into "retrievers".
    monkeypatch.setattr(re_mod, "semantic_search",
                        lambda v, hyde_passages=None: [dict(c, retriever="semantic") for c in SEMANTIC])
    monkeypatch.setattr(re_mod, "keyword_search", lambda v: [dict(c, retriever="keyword") for c in KEYWORD])

    def fake_rerank(q, results):            # cross-encoder stand-in: reverse the fused order
        out = [dict(r, rerank_score=1.0 - i / 10, rank=i) for i, r in enumerate(reversed(results))]
        return out[:15], False

    monkeypatch.setattr(re_mod, "rerank_with_retry", fake_rerank)
    monkeypatch.setattr(re_mod, "mmr_rerank", lambda q, results, top_k: results[1:top_k + 1])
    monkeypatch.setattr(re_mod, "generate_hypothetical_document", lambda q: f"passage about {q}")
    monkeypatch.setattr(re_mod, "load_parent_store", lambda: None)
    monkeypatch.setattr(re_mod.embedder, "enable_embedding_cache", lambda *a: None)
    monkeypatch.setattr(re_mod.embedder, "save_embedding_cache", lambda: None)
    data = tmp_path / "labels.json"
    data.write_text(json.dumps(DATASET), encoding="utf-8")
    return data, tmp_path / "out"


def _run(dataset, out, pipeline, use_hyde=False, name=None):
    payload = re_mod.run_eval(dataset, out, mode="retrieval", k=2, pipeline=pipeline, use_hyde=use_hyde,
                              config_name=name)
    meta, qtraces = read_trace(payload["trace_file"])
    return payload, meta, qtraces


def test_trace_records_run_metadata_and_every_stage(fake_stack):
    dataset, out = fake_stack
    payload, meta, qtraces = _run(dataset, out, "rerank_mmr", name="rerank_mmr")
    assert Path(payload["trace_file"]).with_suffix(".json") == Path(payload["saved_to"])
    assert meta["config"] == {"name": "rerank_mmr", "pipeline": "rerank_mmr", "use_hyde": False,
                              "mode": "retrieval", "k": 2, "judge": False}
    assert meta["labels_sha256"] == labels_sha256(dataset) and meta["index"] and meta["timestamp"]
    assert {"bm25_fold_diacritics", "contextual_chunk_headers", "romanization_english_top_n"} <= set(meta["text_flags"])
    assert meta["summary"] == payload["summary"]
    q1 = qtraces[0]
    assert (q1["id"], q1["config"], q1["scored_stage"]) == ("q1", "rerank_mmr", "mmr")
    assert set(q1["stages"]) == {"fused", "rerank", "mmr"}
    top = q1["stages"]["fused"][0]
    assert set(top) == {"chunk_id", "work", "source", "text_name", "page", "score", "retrievers"}
    assert top["chunk_id"] == "ss_1" and top["work"] == "Sushruta Samhita" and top["page"] == 371
    assert top["retrievers"] == ["semantic", "keyword"]            # found by both
    assert q1["stages"]["rerank"][0]["score"] == 1.0                # stage score = rerank_score


@pytest.mark.parametrize("pipeline, use_hyde", [("rrf", False), ("rerank", False), ("rerank_mmr", False),
                                                ("rerank", True)])
def test_rescoring_a_saved_run_reproduces_its_scores_exactly(fake_stack, pipeline, use_hyde):
    dataset, out = fake_stack
    payload, meta, qtraces = _run(dataset, out, pipeline, use_hyde)
    result = rescore(meta, qtraces, load_labels(dataset))
    assert result["summary"] == payload["summary"]                  # exact, including rounding
    for record in payload["results"]:
        assert {k: result["per_question"][record["id"]][k] for k in record["retrieval"]} == record["retrieval"]


def test_rescoring_against_other_labels_changes_scores(fake_stack, tmp_path):
    dataset, out = fake_stack
    payload, meta, qtraces = _run(dataset, out, "rerank")
    other = tmp_path / "other.json"
    other.write_text(json.dumps([dict(q, gold_sources=["ashtanga_hridaya"]) for q in DATASET]), encoding="utf-8")
    assert rescore(meta, qtraces, load_labels(other))["summary"]["retrieval"]["hit_rate"] == 0.0
    assert payload["summary"]["retrieval"]["hit_rate"] > 0


def test_first_gold_rank(fake_stack):
    dataset, out = fake_stack
    _, meta, qtraces = _run(dataset, out, "rrf")
    labels = load_labels(dataset)
    ranks = {t["id"]: traces.first_gold_rank(t, labels[t["id"]]) for t in qtraces}
    assert ranks == {"q1": 2, "q2": 1, "q3": None}                   # fused: ss_1, api_1, ...


def test_per_question_table_marks_where_rerank_helps_or_hurts(fake_stack):
    dataset, out = fake_stack
    labels = load_labels(dataset)
    _, _, rrf = _run(dataset, out, "rrf")
    _, _, rr = _run(dataset, out, "rerank")
    lines = per_question_table([("rrf", [rrf]), ("rerank", [rr])], labels, (("rrf", "rerank"),))
    rows = {line.split(" | ")[0].strip("| "): line for line in lines if line.startswith("| q")}
    assert rows["q2"].rstrip(" |").endswith("-")                   # rerank pushes the Sushruta chunk down
    assert rows["q3"].rstrip(" |").endswith(".")                   # neither finds Ashtanga Hridaya
    assert any("rerank vs rrf: better" in line for line in lines)


def test_rescore_cli_makes_no_api_calls(fake_stack, monkeypatch, capsys):
    dataset, out = fake_stack
    _run(dataset, out, "rerank")
    from src.ingestion import embedder, pinecone_store
    from src.query import hyde
    from src.reranking import cohere_rerank

    def no_network(*a, **k):
        raise AssertionError("rescore must not touch an API")
    for mod in (embedder, pinecone_store, cohere_rerank, hyde):
        monkeypatch.setattr(mod, "_get_client", no_network)
    spec = importlib.util.spec_from_file_location("rescore", ROOT / "scripts" / "rescore.py")
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    assert cli.main([str(out), "--labels", str(dataset), "--per-question"]) == 0
    printed = capsys.readouterr().out
    assert "same labels" in printed and "Hit@2" in printed and "| q1 |" in printed


def test_comparison_report_includes_before_columns(fake_stack, tmp_path):
    dataset, _ = fake_stack
    spec = importlib.util.spec_from_file_location("run_comparison", ROOT / "scripts" / "run_comparison.py")
    rc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rc)
    before_dir, after_dir = tmp_path / "runs" / "before_1", tmp_path / "runs" / "after_1"
    for d, names in ((before_dir, ("rrf", "rerank")), (after_dir, ("rrf", "rerank"))):
        for name in names:
            re_mod.run_eval(dataset, d, mode="retrieval", k=2, pipeline=name, config_name=name)
    summaries, summary_lines, table = rc.report(rc.load_phase_runs(after_dir), load_labels(dataset),
                                                rc.load_phase_runs(before_dir))
    assert set(summaries) == {"before:rrf", "before:rerank", "rrf", "rerank"}
    assert summary_lines[0] == "| config | Hit@2 | Recall@2 | MRR@2 | MRR@15 |"
    assert "before:rerank" in table[0] and "rerank vs before:rerank" in table[0]


# ── MRR@k: one cutoff for every config ────────────────────────────────

def _synthetic_trace(qid, sources, stage):
    cands = [{"chunk_id": f"{qid}_{i}", "work": None, "source": src, "text_name": None, "page": i, "score": None}
             for i, src in enumerate(sources)]
    return {"type": "question", "id": qid, "question": qid, "gold_sources": [], "config": stage,
            "scored_stage": stage, "scored_n": len(cands), "rerank_skipped": False, "stages": {stage: cands}}


def _meta(pipeline):
    return {"config": {"name": pipeline, "pipeline": pipeline, "k": 6}, "retrieval_params": {"rerank_first_pass_n": 15}}


def test_rerank_and_rerank_mmr_are_scored_on_the_same_cutoff():
    """MRR@6 cuts both lists at 6, although rerank scores 15 candidates and rerank_mmr 6."""
    filler = ["afi_part1.pdf"] * 15
    rerank_list = filler[:8] + ["api_all_volume.pdf"] + filler[9:]          # gold at rank 9 of 15
    mmr_list = filler[:2] + ["api_all_volume.pdf"] + filler[3:6]            # gold at rank 3 of 6
    labels = {"q1": ["api"]}
    rr = rescore(_meta("rerank"), [_synthetic_trace("q1", rerank_list, "rerank")], labels)["per_question"]["q1"]
    mm = rescore(_meta("rerank_mmr"), [_synthetic_trace("q1", mmr_list, "mmr")], labels)["per_question"]["q1"]
    assert rr["mrr_at_k"] == 0.0 and rr["hit"] == 0.0           # rank 9 is past the @6 cutoff ...
    assert rr["mrr"] == pytest.approx(1 / 9)                     # ... but counts in the full-list MRR@15
    assert mm["mrr_at_k"] == pytest.approx(1 / 3) and mm["hit"] == 1.0
    assert mm["mrr"] == mm["mrr_at_k"]                           # a 6-deep list: full-list MRR = MRR@6


def test_summary_table_headlines_mrr_at_6_and_marks_mrr_at_15_na_for_mmr():
    labels = {"q1": ["api"]}
    lists = {"rerank": ["api_all_volume.pdf"] + ["afi_part1.pdf"] * 14, "rerank_mmr": ["api_all_volume.pdf"] * 6}
    groups = [(p, [(_meta(p), rescore(_meta(p), [_synthetic_trace("q1", lst, "rerank" if p == "rerank" else "mmr")],
                                     labels)["summary"])]) for p, lst in lists.items()]
    lines = summary_table(groups)
    assert lines[0] == "| config | Hit@6 | Recall@6 | MRR@6 | MRR@15 |"
    assert lines[2] == "| rerank | 1.000 | 1.000 | 1.000 | 1.000 |"
    assert lines[3] == "| rerank_mmr | 1.000 | 1.000 | 1.000 | n/a |"


def test_eval_runs_score_mrr_at_k_on_the_cutoff_for_every_pipeline(fake_stack):
    dataset, out = fake_stack
    labels = load_labels(dataset)
    for pipeline in ("rrf", "rerank", "rerank_mmr"):
        payload, meta, qtraces = _run(dataset, out, pipeline)
        k = meta["config"]["k"]
        by_id = {r["id"]: r["retrieval"] for r in payload["results"]}
        for t in qtraces:
            rank = traces.first_gold_rank(t, labels[t["id"]])
            expected = 1 / rank if rank and rank <= k else 0.0
            assert by_id[t["id"]]["mrr_at_k"] == expected, (pipeline, t["id"], rank)
