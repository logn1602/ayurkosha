"""Spelling-variant matching: diacritic folding + romanization keys in BM25.

The synonym dictionaries use popular romanization ("Ashwagandha"), the
Pharmacopoeia IAST ("Aśvagandhā"), the Formulary folded-IAST ASCII
("asvagandha"). These tests pin down that all three meet, for documents,
queries and dictionary lookups alike.

Run: python -m pytest tests/test_romanization.py
"""

import pytest

from config.settings import settings
from src.ingestion.bm25_store import build_bm25_index
from src.ingestion.synonym_loader import get_synonyms
from src.retrieval.tokenizer import tokenize_ayurvedic
from src.utils.transliterate import romanization_key

CHUNKS = [
    # No Latin binomial here: the match must come from the Sanskrit name alone.
    {"chunk_id": "api_asvagandha", "text": "Aśvagandhā consists of dried mature roots.", "metadata": {}},
    {"chunk_id": "ss_gokshura", "text": "The Gokshura subdues the deranged Vayu.", "metadata": {}},
    {"chunk_id": "afi_satavari", "text": "satavari rasa (satavari) (rt. tr.) 768 ml.", "metadata": {}},
    {"chunk_id": "other_1", "text": "Treatment of fever with fasting and light diet.", "metadata": {}},
    {"chunk_id": "other_2", "text": "Pippali is the best of pungent drugs.", "metadata": {}},
]


@pytest.fixture
def folding(monkeypatch):
    monkeypatch.setattr(settings, "bm25_fold_diacritics", True)


@pytest.mark.parametrize("spellings, key", [
    (["ashwagandha", "asvagandha"], "asvagandha"),
    (["shatavari", "satavari"], "satavar"),
    (["guduchi", "guduci"], "guduci"),
    (["gokshura", "goksura"], "goksura"),
    (["krishna", "krsna"], "krsna"),
    (["ghrita", "ghrta"], "ghrta"),
])
def test_romanization_key_unifies_spellings(spellings, key):
    assert {romanization_key(s) for s in spellings} == {key}


def test_romanization_key_leaves_short_and_non_alpha_tokens():
    assert romanization_key("sh") == "sh"
    assert romanization_key("x2w") == "x2w"


def test_ashwagandha_matches_indexed_iast_asvagandha(folding):
    hits = build_bm25_index(CHUNKS).search("Ashwagandha", top_n=3)
    assert hits and hits[0]["chunk_id"] == "api_asvagandha"


def test_diacritic_query_matches_popular_spelling(folding):
    hits = build_bm25_index(CHUNKS).search("Gokṣura", top_n=3)          # query folded too
    assert hits and hits[0]["chunk_id"] == "ss_gokshura"


def test_popular_query_matches_formulary_ascii(folding):
    hits = build_bm25_index(CHUNKS).search("Shatavari", top_n=3)
    assert hits and hits[0]["chunk_id"] == "afi_satavari"


def test_without_folding_iast_document_is_missed(monkeypatch):
    monkeypatch.setattr(settings, "bm25_fold_diacritics", False)
    hits = build_bm25_index(CHUNKS).search("Ashwagandha", top_n=3)
    assert all(h["chunk_id"] != "api_asvagandha" for h in hits)


def test_synonym_dictionary_lookup_is_folded_and_keyed(folding):
    for spelling in ("Ashwagandha", "asvagandha", "Aśvagandhā", "ashvagandha"):
        assert "Withania somnifera" in get_synonyms(spelling), spelling


def test_document_and_query_tokens_share_the_key(folding):
    doc = set(tokenize_ayurvedic("Aśvagandhā", stem=False))
    query = set(tokenize_ayurvedic("Ashwagandha", stem=False))
    assert "asvagandha" in doc & query


# ── keys are for Sanskrit-like tokens only ────────────────────────────

@pytest.mark.parametrize("word, collision", [
    ("ship", "sip"), ("wine", "vine"), ("shore", "sore"), ("food", "fud"), ("teeth", "tith"),
])
def test_english_words_get_no_romanization_key(folding, word, collision):
    assert collision not in tokenize_ayurvedic(word, stem=False)


def test_ship_does_not_match_sip_but_ashwagandha_matches_asvagandha(folding):
    chunks = CHUNKS + [{"chunk_id": "sip", "text": "Take a small sip of warm water.", "metadata": {}}]
    index = build_bm25_index(chunks)
    assert all(h["chunk_id"] != "sip" for h in index.search("ship", top_n=5))
    assert index.search("Ashwagandha", top_n=1)[0]["chunk_id"] == "api_asvagandha"


def test_which_tokens_get_keys(folding):
    from src.ingestion.synonym_loader import wants_romanization_key
    assert not wants_romanization_key("ship")                     # common English word
    assert wants_romanization_key("krishna")                      # dictionary Sanskrit term (also common in English)
    assert wants_romanization_key("satavari")                     # not an English word
    assert wants_romanization_key("ship", frozenset({"ship"}))    # written with diacritics in the source


def test_unknown_word_whose_key_is_english_gets_no_key(folding):
    from src.ingestion.synonym_loader import wants_romanization_key
    from src.utils.transliterate import english_words
    assert "braches" not in english_words() and "braces" in english_words()
    assert not wants_romanization_key("braches", key="braces")
    assert "braces" not in tokenize_ayurvedic("braches", stem=False)
