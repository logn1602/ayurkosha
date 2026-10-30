"""Tests for scripts/run_comparison.py: budget, run counts, phase checks (offline).

Run: python -m pytest tests/test_run_comparison.py
"""

import importlib.util
import sys
from pathlib import Path

import pytest

from config.settings import settings

_SPEC = importlib.util.spec_from_file_location(
    "run_comparison", Path(__file__).resolve().parents[1] / "scripts" / "run_comparison.py")
rc = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(rc)


def test_only_hyde_configs_repeat():
    assert [rc.runs_for(c, 3) for c in rc.PHASES["after"]] == [1, 1, 1, 3]
    assert [rc.runs_for(c, 3) for c in rc.PHASES["before"]] == [1, 1]


def test_phase_estimates():
    before = rc.estimate_calls(rc.PHASES["before"], 30, cached_queries=0)
    assert before["cohere"] == {"query_embed": 30, "rerank": 30, "mmr_embed": 0, "hyde_embed": 0, "total": 60}
    after = rc.estimate_calls(rc.PHASES["after"], 30, cached_queries=30)
    # rerank: rerank + rerank_mmr + 3 HyDE runs = 5 x 30
    assert after["cohere"] == {"query_embed": 0, "rerank": 150, "mmr_embed": 30, "hyde_embed": 90, "total": 270}
    assert after["claude_haiku"] == 90


def test_full_budget_fits_with_margin():
    b = rc.full_budget(30, cached_queries=0)
    assert (b["before"], b["reingest"], b["after"]) == (60, 237, 270)
    assert b["total"] == 567 and b["margin"] == 433
    assert b["total"] <= 0.6 * rc.TRIAL_CALLS_PER_MONTH


def test_reingest_plan_quotes_the_same_comparison_budget():
    spec = importlib.util.spec_from_file_location(
        "reingest", Path(__file__).resolve().parents[1] / "scripts" / "reingest.py")
    reingest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reingest)
    b = rc.full_budget(30, cached_queries=0)
    assert reingest.COMPARISON_CALLS == b["before"] + b["after"]
    assert b["reingest"] + reingest.COMPARISON_CALLS == b["total"]


@pytest.mark.parametrize("phase, vectors, chunks, headers, ok", [
    ("before", 46827, 46826, False, True),    # old index + old stores (1 stray vector)
    ("before", 46827, 22718, True, False),    # new stores promoted already
    ("before", 46827, 46826, True, False),    # headers mean the new build
    ("after", 22718, 22718, True, True),      # new index + new stores
    ("after", 46827, 22718, True, False),     # .env still points at the old index
    ("after", 22718, 22718, False, False),    # stores not promoted
])
def test_consistency_checks(phase, vectors, chunks, headers, ok):
    assert (rc.consistency_error(phase, vectors, chunks, headers) is None) == ok


def test_before_phase_turns_every_new_text_flag_off(monkeypatch, capsys):
    for flag in rc.NEW_TEXT_FLAGS:
        monkeypatch.setattr(settings, flag, True)          # restored at teardown
    monkeypatch.setattr(sys, "argv", ["run_comparison.py", "--phase", "before"])
    rc.main()                                              # dry run: no API calls
    assert all(getattr(settings, f) is False for f in rc.NEW_TEXT_FLAGS)
    out = capsys.readouterr().out
    # The exact total depends on how many query embeddings are cached already.
    assert "DRY RUN" in out and "of 1000/month" in out and "bm25_fold_diacritics=False" in out


def test_after_phase_keeps_flags(monkeypatch):
    for flag in rc.NEW_TEXT_FLAGS:
        monkeypatch.setattr(settings, flag, True)
    monkeypatch.setattr(sys, "argv", ["run_comparison.py", "--phase", "after"])
    rc.main()
    assert all(getattr(settings, f) is True for f in rc.NEW_TEXT_FLAGS)
