"""Tests the exclude_charaka switch in src/ingestion/pipeline.py.

Runs ingestion over a temp folder with embed=False, with the store saves stubbed
so the real data/cache indexes are never touched.

Run: python -m pytest tests/test_pipeline_exclusion.py
"""

from config.settings import settings
from src.ingestion import bm25_store, parent_store, pipeline


def _run(tmp_path, monkeypatch, exclude):
    (tmp_path / "charaka_samhita_test.txt").write_text("Charaka text about fever and its treatment. " * 5)
    (tmp_path / "sushruta_samhita_test.txt").write_text("Sushruta text about cough and its treatment. " * 5)
    saved = {}
    monkeypatch.setattr(parent_store, "save_parent_store", lambda store, *a, **k: saved.setdefault("parents", store))
    monkeypatch.setattr(bm25_store, "save_bm25_index", lambda index, *a, **k: saved.setdefault("bm25", index))
    monkeypatch.setattr(settings, "exclude_charaka", exclude)
    stats = pipeline.run_ingestion(data_dir=tmp_path, embed=False)
    sources = {c["metadata"]["source"] for c in saved["bm25"].chunks}
    return stats, sources


def test_charaka_skipped_when_excluded(tmp_path, monkeypatch):
    stats, sources = _run(tmp_path, monkeypatch, exclude=True)
    assert stats["excluded_files"] == 1 and stats["files"] == 1
    assert sources == {"sushruta_samhita_test.txt"}


def test_charaka_indexed_when_flag_off(tmp_path, monkeypatch):
    stats, sources = _run(tmp_path, monkeypatch, exclude=False)
    assert stats["excluded_files"] == 0 and stats["files"] == 2
    assert sources == {"charaka_samhita_test.txt", "sushruta_samhita_test.txt"}
