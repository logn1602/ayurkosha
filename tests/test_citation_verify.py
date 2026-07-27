"""Tests for src/generation/citation_verify.py.

Run: python -m pytest tests/test_citation_verify.py
"""

from src.generation.citation_verify import verify_citations


def _sources(n):
    return [{"citation_number": i, "document": f"doc-{i}", "page": i, "heading": None}
            for i in range(1, n + 1)]


def test_valid_citations_pass():
    answer = "Amavata is treated with Guggulu【1】 and diet changes【2】."
    result = verify_citations(answer, _sources(2))
    assert result["answer"] == answer
    assert result["hallucinated_citations"] == []
    assert [s["citation_number"] for s in result["used_sources"]] == [1, 2]


def test_hallucinated_citations_stripped():
    answer = "Guggulu helps with joint pain【1】 and also cures everything【5】."
    result = verify_citations(answer, _sources(1))
    assert "【5】" not in result["answer"]
    assert "【1】" in result["answer"]
    assert result["hallucinated_citations"] == [5]
    assert [s["citation_number"] for s in result["used_sources"]] == [1]


def test_no_citations():
    answer = "No sources were cited here."
    result = verify_citations(answer, _sources(3))
    assert result["answer"] == answer
    assert result["used_sources"] == []
    assert result["hallucinated_citations"] == []


def test_repeated_citation_only_used_once():
    answer = "Claim one【1】. Claim two also references it【1】."
    result = verify_citations(answer, _sources(2))
    assert len(result["used_sources"]) == 1
    assert result["used_sources"][0]["citation_number"] == 1
