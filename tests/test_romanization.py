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
