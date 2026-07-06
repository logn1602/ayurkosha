"""Tests for the Ayurvedic tokenizer and synonym loader.

These tests require the synonym dictionaries to have been generated first:
    python scripts/build_synonyms.py
Run from the project root with:  python -m pytest tests/test_tokenizer.py
"""

import pytest

from src.retrieval.tokenizer import tokenize_ayurvedic
from src.ingestion.synonym_loader import get_synonyms


# ── Base tokenization (starter tests, must keep passing) ──────────────

def test_basic_tokenization():
    tokens = tokenize_ayurvedic("Ashwagandha is good for health")
    assert "ashwagandha" in tokens
    assert "health" in tokens
    assert "is" not in tokens  # stopword removed


def test_devanagari_tokenization():
    tokens = tokenize_ayurvedic("अश्वगंधा is a Rasayana herb")
    assert "अश्वगंधा" in tokens
    assert "rasayana" in tokens


def test_stopword_removal():
    tokens = tokenize_ayurvedic("the herb is in the formulation")
    assert "the" not in tokens
    assert "is" not in tokens
    assert "in" not in tokens
    assert "herb" in tokens
    assert "formulation" in tokens  # surface form preserved (stemming is additive)


# ── Synonym expansion ─────────────────────────────────────────────────

def test_synonym_expansion_herb():
    # "Amla" (Hindi) should expand to its Sanskrit and Latin/English variants.
    tokens = tokenize_ayurvedic("Amla is good for digestion")
    assert "amla" in tokens          # original surface form retained
    assert "amalaki" in tokens       # Sanskrit synonym
    assert "emblica" in tokens       # from Latin binomial "Emblica officinalis"
    assert "gooseberry" in tokens    # from English "Indian Gooseberry"


def test_synonym_expansion_disease():
    # "Amavata" maps to the arthritis entry (Ayurvedic <-> modern).
    tokens = tokenize_ayurvedic("Amavata chikitsa")
    assert "amavata" in tokens
    assert "sandhivata" in tokens    # sibling Ayurvedic synonym
    assert "arthritis" in tokens     # from modern "Rheumatoid Arthritis"


def test_synonym_expansion_can_be_disabled():
    tokens = tokenize_ayurvedic("Amla juice", expand_synonyms=False)
    assert "amla" in tokens
    assert "amalaki" not in tokens


def test_unknown_term_not_expanded():
    tokens = tokenize_ayurvedic("Zqxwv remedy")
    assert "zqxwv" in tokens


# ── Domain acronyms ───────────────────────────────────────────────────

def test_domain_acronym_preserved():
    # "API" = Ayurvedic Pharmacopoeia of India; must survive intact and not be
    # sent through synonym expansion or stemming.
    tokens = tokenize_ayurvedic("API monograph for Guduchi")
    assert "api" in tokens


# ── Stemming (requires NLTK) ──────────────────────────────────────────

def test_additive_stemming():
    pytest.importorskip("nltk")
    tokens = tokenize_ayurvedic("formulations", expand_synonyms=False, stem=True)
    assert "formulations" in tokens  # surface form kept
    assert "formul" in tokens        # Porter stem added alongside


def test_stemming_matches_related_forms():
    pytest.importorskip("nltk")
    configuring = tokenize_ayurvedic("configuring", expand_synonyms=False)
    configuration = tokenize_ayurvedic("configuration", expand_synonyms=False)
    # The two surface forms share a common stem, enabling BM25 to match them.
    assert set(configuring) & set(configuration)


def test_devanagari_never_stemmed():
    tokens = tokenize_ayurvedic("अश्वगंधा", stem=True)
    assert tokens == ["अश्वगंधा"]


# ── Synonym loader ────────────────────────────────────────────────────

def test_get_synonyms_includes_all_variants():
    syns = get_synonyms("amla")
    assert "Amalaki" in syns
    assert "Emblica officinalis" in syns
    assert "amla" in syns  # the queried term is always included


def test_get_synonyms_unknown_returns_self():
    assert get_synonyms("notaherb") == {"notaherb"}


def test_get_synonyms_case_insensitive():
    # Lookup is case-insensitive: both casings resolve to the same variant set
    # (the only difference is the verbatim self-term that is always included).
    upper = get_synonyms("AMLA")
    lower = get_synonyms("amla")
    assert "Amalaki" in upper and "Amalaki" in lower
    assert upper - {"AMLA"} == lower - {"amla"}
