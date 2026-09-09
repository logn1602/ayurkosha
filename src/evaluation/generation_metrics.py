"""
AyurKosha — Generation Quality Metrics
Deterministic, no-API checks on a generated answer.

These are the metrics that can be computed without a second LLM call:
citation accuracy (reusing the Phase-4 citation verifier), a lexical
grounding proxy for faithfulness, safety-disclaimer presence, and a lexical
question-overlap proxy for relevance. The *semantic* judgments —
faithfulness, relevance, completeness as a human would score them — are the
job of the LLM judge (src/evaluation/llm_judge.py); the two proxies here are
cheap sanity signals, explicitly labelled as proxies, not replacements.

Build this in: Phase 6
"""

from __future__ import annotations

import re
from typing import Any

from src.generation.citation_verify import verify_citations

# Short, high-frequency words excluded from lexical-overlap proxies so the
# scores reflect content terms, not glue words.
_STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "is", "are", "for",
    "what", "which", "how", "with", "on", "at", "by", "be", "as", "it",
    "this", "that", "from", "was", "were", "will", "can", "do", "does",
}

_WORD_RE = re.compile(r"[a-z]+")

# Practitioner-guidance disclaimer marker (from src/generation/prompts.py).
_DISCLAIMER_MARKER = "qualified"
_DISCLAIMER_MARKER2 = "practitioner"


def _content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower())
            if len(w) > 2 and w not in _STOPWORDS}


def citation_accuracy(answer: str, sources: list[dict[str, Any]]) -> float:
    """Fraction of citation markers in the answer that map to a real source.

    Reuses src/generation/citation_verify.verify_citations. Returns 1.0 when
    the answer contains no citation markers at all (vacuously accurate).
    """
    result = verify_citations(answer, sources)
    used = len(result["used_sources"])
    hallucinated = len(result["hallucinated_citations"])
    total = used + hallucinated
    return 1.0 if total == 0 else used / total


def hallucinated_citation_count(answer: str, sources: list[dict[str, Any]]) -> int:
    """Number of distinct citation markers pointing to non-existent sources."""
    return len(verify_citations(answer, sources)["hallucinated_citations"])


def grounding_proxy(answer: str, context_block: str) -> float:
    """Lexical faithfulness proxy: fraction of the answer's content words that
    also appear in the provided context.

    A high value means most of what the answer says is lexically present in
    the sources; a low value flags text that may be ungrounded. This is a
    cheap heuristic — the LLM judge measures true faithfulness.
    """
    answer_words = _content_words(answer)
    if not answer_words:
        return 0.0
    context_words = _content_words(context_block)
    return len(answer_words & context_words) / len(answer_words)


def relevance_proxy(answer: str, question: str) -> float:
    """Lexical relevance proxy: fraction of the question's content words that
    appear in the answer. Cheap heuristic; the LLM judge is authoritative.
    """
    question_words = _content_words(question)
    if not question_words:
        return 0.0
    answer_words = _content_words(answer)
    return len(question_words & answer_words) / len(question_words)


def has_safety_disclaimer(answer: str) -> bool:
    """Whether the mandatory practitioner-guidance disclaimer is present."""
    low = answer.lower()
    return _DISCLAIMER_MARKER in low and _DISCLAIMER_MARKER2 in low


def score_generation(
    answer: str,
    question: str,
    context_block: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """Compute all deterministic generation metrics for one answer."""
    return {
        "citation_accuracy": citation_accuracy(answer, sources),
        "hallucinated_citations": hallucinated_citation_count(answer, sources),
        "grounding_proxy": grounding_proxy(answer, context_block),
        "relevance_proxy": relevance_proxy(answer, question),
        "has_safety_disclaimer": has_safety_disclaimer(answer),
    }
