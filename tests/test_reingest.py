"""Tests for scripts/reingest.py and pipeline.build_corpus (all offline, faked services).

Run: python -m pytest tests/test_reingest.py
"""

import importlib.util
from pathlib import Path

import pytest

from config.settings import settings
from src.ingestion import bm25_store, parent_store, pipeline
from src.ingestion.embedder import CohereQuotaExhausted

_SPEC = importlib.util.spec_from_file_location(
    "reingest", Path(__file__).resolve().parents[1] / "scripts" / "reingest.py")
reingest = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(reingest)

_REAL_CACHE = reingest.CACHE_DIR


def _fingerprint():
    return {p.name: (p.stat().st_size, p.stat().st_mtime) for p in _REAL_CACHE.iterdir()}


@pytest.fixture(autouse=True)
def real_cache_untouched():
    """Every test here must leave the real data/cache exactly as it was."""
    before = _fingerprint()
    yield
    assert _fingerprint() == before, "a test modified the real data/cache"


def _corpus_dir(tmp_path):
    src = tmp_path / "raw"
    src.mkdir()
    (src / "sushruta_samhita_test.txt").write_text("Chap.IX.]CHIKITSASTHANAM. Kushtha treatment with Khadira. " * 40)
    (src / "charaka_samhita_test.txt").write_text("garbled text layer " * 40)
    return src


def test_build_corpus_is_offline_and_writes_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("build_corpus must not write stores")
    monkeypatch.setattr(parent_store, "save_parent_store", boom)
    monkeypatch.setattr(bm25_store, "save_bm25_index", boom)
    monkeypatch.setattr(settings, "exclude_charaka", True)
    corpus = pipeline.build_corpus(_corpus_dir(tmp_path))
    assert list(corpus["per_source"]) == ["sushruta_samhita_test.txt"]
    assert corpus["excluded"][0][0] == "charaka_samhita_test.txt"
    assert corpus["stats"]["children"] == len(corpus["children"]) > 0


def test_plan_counts_batches_of_96():
    corpus = {"children": [{"text": "x" * 400, "metadata": {}} for _ in range(200)]}
    est = reingest.plan(corpus)
    assert est["embed_calls"] == 3 and est["children"] == 200
    assert est["tokens"] == 200 * 400 // 4


def test_run_refuses_the_live_index(monkeypatch):
    monkeypatch.setattr(settings, "pinecone_index_name", "ayurkosha")
    assert reingest.run("ayurkosha") == 1


class _FakeIndex:
    def __init__(self, count):
        self.count = count

    def describe_index_stats(self):
        return {"total_vector_count": self.count}


@pytest.fixture
def fake_env(tmp_path, monkeypatch):
    from src.ingestion import pinecone_store
    cache = tmp_path / "cache"
    cache.mkdir()
    for name in reingest.STORE_FILES:
        (cache / name).write_text("old")
    monkeypatch.setattr(reingest, "CACHE_DIR", cache)
    monkeypatch.setattr(settings, "pinecone_index_name", "ayurkosha")
    monkeypatch.setattr(reingest.time, "sleep", lambda s: None)
    index = _FakeIndex(0)
    monkeypatch.setattr(pinecone_store, "ensure_index", lambda name=None, wait=True: index)
    return cache, index


def _fake_ingestion(index, children, raise_exc=None):
    def fake(**kwargs):
        if raise_exc:
            raise raise_exc
        for name in reingest.STORE_FILES:
            (Path(kwargs["store_dir"]) / name).write_text("new")
        index.count = children
        return {"children": children}
    return fake


def test_quota_stop_keeps_live_stores(fake_env, monkeypatch):
    cache, index = fake_env
    monkeypatch.setattr(reingest, "run_ingestion", _fake_ingestion(index, 10, CohereQuotaExhausted("quota")))
    assert reingest.run("ayurkosha-v2") == 2
    assert all((cache / n).read_text() == "old" for n in reingest.STORE_FILES)


def test_incomplete_index_is_not_promoted(fake_env, monkeypatch):
    cache, index = fake_env

    def partial(**kwargs):
        result = _fake_ingestion(index, 10)(**kwargs)
        index.count = 7                        # some vectors missing
        return result
    monkeypatch.setattr(reingest, "run_ingestion", partial)
    assert reingest.run("ayurkosha-v2") == 3
    assert all((cache / n).read_text() == "old" for n in reingest.STORE_FILES)


def test_success_promotes_with_backup(fake_env, monkeypatch):
    cache, index = fake_env
    monkeypatch.setattr(reingest, "run_ingestion", _fake_ingestion(index, 10))
    assert reingest.run("ayurkosha-v2") == 0
    assert all((cache / n).read_text() == "new" for n in reingest.STORE_FILES)
    backups = list(cache.glob("backup_*"))
    assert len(backups) == 1 and all((backups[0] / n).read_text() == "old" for n in reingest.STORE_FILES)
