"""Tests for src/generation/safety.py pure logic (no API calls).

The contraindication retrieval path (semantic_search) needs the live
Pinecone/Cohere APIs and is exercised by the end-to-end /query run rather than
here — these tests cover only the deterministic helpers.

Run: python -m pytest tests/test_safety.py
"""

from src.generation import safety
from src.generation.safety import (
    _PRACTITIONER_DISCLAIMER,
    _relevant_sentences,
    apply_safety_checks,
    find_mentioned_herbs,
)


def test_find_mentioned_herbs_detects_known_variant():
    herbs = find_mentioned_herbs("Amla is a rich source of vitamin C.")
    assert any(h.lower() == "amla" for h in herbs)


def test_find_mentioned_herbs_case_insensitive():
    herbs = find_mentioned_herbs("ashwagandha supports vitality")
    assert any("ashwagandha" in h.lower() for h in herbs)


def test_find_mentioned_herbs_none_for_unrelated_text():
    assert find_mentioned_herbs("This text mentions no herbs at all.") == []


def test_relevant_sentences_picks_safety_keyword_sentences():
    text = ("It is generally well tolerated. It is contraindicated in pregnancy. "
            "It tastes bitter.")
    hits = _relevant_sentences(text)
    assert any("contraindicated" in s for s in hits)
    assert not any("tastes bitter" in s for s in hits)


def test_apply_safety_checks_appends_disclaimer_when_missing():
    # No herbs mentioned -> no retrieval; disclaimer must still be appended.
    out = apply_safety_checks("A generic answer with no herb names.", [])
    assert _PRACTITIONER_DISCLAIMER in out


def test_apply_safety_checks_does_not_duplicate_disclaimer():
    answer = f"Some answer. {_PRACTITIONER_DISCLAIMER}"
    out = apply_safety_checks(answer, [])
    assert out.count(_PRACTITIONER_DISCLAIMER) == 1


def test_apply_safety_checks_flags_rasa_shastra_from_sources():
    answer = "Take this bhasma preparation daily."
    out = apply_safety_checks(answer, [])
    assert "expert preparation and supervision" in out
