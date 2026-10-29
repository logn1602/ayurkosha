"""Tests for src/reranking/cohere_rerank.py retry / pacing / fallback logic.

The Cohere client and time.sleep are faked — no live API calls, no waiting.

Run: python -m pytest tests/test_cohere_rerank.py
"""

from types import SimpleNamespace

import pytest

from config.settings import settings
from src.reranking import cohere_rerank as cr

CANDIDATES = [{"chunk_id": f"c{i}", "text": f"passage {i}"} for i in range(4)]


class _FakeClient:
    """Raises the queued errors in order, then returns a reversed ranking."""

    def __init__(self, errors=()):
        self.errors = list(errors)
        self.calls = 0

    def rerank(self, query, documents, top_n, model):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        order = list(range(len(documents)))[::-1][:top_n]
        return SimpleNamespace(results=[
            SimpleNamespace(index=i, relevance_score=1.0 - n / 10) for n, i in enumerate(order)
        ])


@pytest.fixture
def fake(monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(cr.time, "sleep", sleeps.append)
    monkeypatch.setattr(cr, "_last_call_at", None)
    monkeypatch.setattr(settings, "rerank_max_retries", 3)
    monkeypatch.setattr(settings, "rerank_backoff_base", 6.0)
    monkeypatch.setattr(settings, "cohere_rerank_calls_per_min", 0)

    def install(errors=()):
        client = _FakeClient(errors)
        monkeypatch.setattr(cr, "_get_client", lambda: client)
        return client

    install.sleeps = sleeps
    return install


def _rate_limit():
    return RuntimeError("status_code: 429, Trial key limited to 10 API calls / minute")


def test_retry_succeeds_after_rate_limits_with_exponential_backoff(fake):
    client = fake([_rate_limit(), _rate_limit()])
    out, skipped = cr.rerank_with_retry("q", CANDIDATES, top_n=2)
    assert not skipped
    assert client.calls == 3
    assert fake.sleeps == [6.0, 12.0]
    assert [r["chunk_id"] for r in out] == ["c3", "c2"]
    assert out[0]["rerank_score"] == 1.0


def test_retry_exhausted_marks_skipped(fake):
    client = fake([_rate_limit()] * 10)
    out, skipped = cr.rerank_with_retry("q", CANDIDATES, top_n=2)
    assert skipped
    assert client.calls == 4                    # 1 try + 3 retries
    assert [r["chunk_id"] for r in out] == ["c0", "c1"]   # unranked fallback


def test_non_rate_limit_error_skips_without_retry(fake):
    client = fake([ValueError("bad request")])
    out, skipped = cr.rerank_with_retry("q", CANDIDATES, top_n=2)
    assert skipped
    assert client.calls == 1
    assert fake.sleeps == []


def test_pacing_spaces_calls_by_configured_rate(fake, monkeypatch):
    fake()
    monkeypatch.setattr(settings, "cohere_rerank_calls_per_min", 10)
    clock = iter([100.0, 101.0, 101.0])
    monkeypatch.setattr(cr.time, "monotonic", lambda: next(clock))
    cr.rerank_with_retry("q", CANDIDATES)       # first call: no wait
    cr.rerank_with_retry("q", CANDIDATES)       # 1s later: wait the other 5s
    assert fake.sleeps == [pytest.approx(5.0)]


def test_production_rerank_still_falls_back_without_retry(fake):
    client = fake([_rate_limit()])
    out = cr.rerank("q", CANDIDATES, top_n=2)
    assert client.calls == 1
    assert [r["chunk_id"] for r in out] == ["c0", "c1"]


def test_empty_results(fake):
    assert cr.rerank_with_retry("q", []) == ([], False)
