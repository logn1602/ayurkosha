"""Tests for src/ingestion/text_cleanup.py (pure text functions, no I/O).

Run: python -m pytest tests/test_text_cleanup.py
"""

from config.settings import settings
from src.ingestion import text_cleanup as tc

API = "Ayurvedic Pharmacopoeia of India"


# ── legacy-font map ───────────────────────────────────────────────────

def test_api_property_block_decodes_to_iast():
    raw = "Rasa : Ka¶u\nGu¸a : R£kÀa\nV¢rya : UÀ¸a\nVip¡ka : Ka¶u\nKarma : B¤Æha¸a"
    assert tc.fix_font_artifacts(raw, API) == (
        "Rasa : Kaṭu\nGuṇa : Rūkṣa\nVīrya : Uṣṇa\nVipāka : Kaṭu\nKarma : Bṛṃhaṇa")


def test_api_titles_and_herb_names():
    assert tc.fix_font_artifacts("AáVAGANDHË (Root)", API) == "AŚVAGANDHĀ (Root)"
    assert tc.fix_font_artifacts("A¿vagandh¡", API) == "Aśvagandhā"
    assert tc.fix_font_artifacts("GUÚÍCÌ (Stem)", API) == "GUḌŪCĪ (Stem)"


def test_api_micron_and_degree_kept_outside_words():
    raw = "cells upto 35 µ in diameter; dried at 105°C; Karaµja, L°hitapuÀpa; 35 ƒÊm"
    assert tc.fix_font_artifacts(raw, API) == (
        "cells upto 35 µ in diameter; dried at 105°C; Karañja, Lohitapuṣpa; 35 µm")


def test_classical_ocr_pound_is_long_a_and_soft_hyphen_joined():
    raw = "the V£yu and vid£rigandha; look upon our\xad selves"
    assert tc.fix_font_artifacts(raw, "Sushruta Samhita") == (
        "the Vāyu and vidārigandha; look upon ourselves")


def test_afi_gram_unit_after_quantity_only():
    raw = "16. bibhitaka (p.) 24 £. 17. amalaki 960£; Dr. G. £. Karandikar"
    assert tc.fix_font_artifacts(raw, "Ayurvedic Formulary of India") == (
        "16. bibhitaka (p.) 24 g. 17. amalaki 960g; Dr. G. £. Karandikar")


def test_unmapped_work_unchanged():
    raw = "Gu¸a £ 12"
    assert tc.fix_font_artifacts(raw, "Charaka Samhita") == raw
    assert tc.fix_font_artifacts(raw, None) == raw


def test_apply_font_fixes_is_gated(monkeypatch):
    rec = {"text": "V¢rya", "metadata": {"source": "api_all_volume.pdf"}}
    monkeypatch.setattr(settings, "apply_font_char_map", False)
    tc.apply_font_fixes([rec])
    assert rec["text"] == "V¢rya"
    monkeypatch.setattr(settings, "apply_font_char_map", True)
    tc.apply_font_fixes([rec])
    assert rec["text"] == "Vīrya"


# ── diacritic folding ─────────────────────────────────────────────────

def test_fold_diacritics_latin_only():
    assert tc.fold_diacritics("Aśvagandhā Ṛṣyaproktā") == "Asvagandha Rsyaprokta"
    assert tc.fold_diacritics("गुडूची") == "गुडूची"        # Devanagari matras preserved


def test_tokenizer_folds_when_enabled(monkeypatch):
    from src.retrieval.tokenizer import tokenize_ayurvedic
    monkeypatch.setattr(settings, "bm25_fold_diacritics", True)
    assert tokenize_ayurvedic("Aśvagandhā", expand_synonyms=False, stem=False) == ["asvagandha"]
    monkeypatch.setattr(settings, "bm25_fold_diacritics", False)
    assert tokenize_ayurvedic("Aśvagandhā", expand_synonyms=False, stem=False) == ["vagandh"]
