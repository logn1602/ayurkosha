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


# ── run-together OCR word splitting ───────────────────────────────────

import pytest


@pytest.fixture(scope="module")
def splitter():
    spaced = {"spaced.pdf": ["Pindaluka and Madhviluka are cooling. Prithak parni, Priyangu. "
                             "Ghritam Ghritam Ghritam haemoptysis haemoptysis haemoptysis. A medicated oil."] * 3}
    vocab = tc.build_protected_vocab(spaced, extra_words=["Kakolyadi"])
    return tc.GluedWordSplitter(vocab)


def test_splits_glued_english(splitter):
    assert (splitter.split("Nowweshalldiscourseonthemedicaltreatmentofhaemorrhoids")
            == "Now we shall discourse on the medical treatment of haemorrhoids")


def test_keeps_capitalized_sanskrit_names_whole(splitter):
    assert splitter.split("Pindaluka,Madhviluka,Hastyaluka") == "Pindaluka,Madhviluka,Hastyaluka"
    assert splitter.split("AmedicatedGhritam") == "A medicated Ghritam"
    assert splitter.split("IndivaraandUtpala") == "Indivara and Utpala"


def test_unknown_word_inside_run_stays_whole(splitter):
    out = splitter.split("preparedwiththePrithak")
    assert out == "prepared with the Prithak"


def test_short_or_known_runs_untouched(splitter):
    assert splitter.split("Vasti, Kapham") == "Vasti, Kapham"
    assert splitter.split("haemoptysis") == "haemoptysis"


def test_glued_sources_do_not_teach_vocab():
    glued = {"glued.pdf": ["andthederangedvayuandthederangedpittam " * 5]}
    spaced = {"ok.pdf": ["the deranged vayu and pittam " * 5]}
    assert tc.glued_run_ratio(glued["glued.pdf"]) > tc.GLUED_SOURCE_RATIO
    vocab = tc.build_protected_vocab({**glued, **spaced})
    assert "vayu" in vocab and not any(len(w) >= tc.GLUE_MIN_RUN for w in vocab)


def test_add_bm25_text_gated_and_keeps_raw_text(monkeypatch):
    children = [{"chunk_id": "c1", "text": "Nowweshalldiscourseonthetreatment",
                 "metadata": {"source": "sushruta_samhita_vol_2.pdf"}}]
    monkeypatch.setattr(settings, "split_glued_ocr_words", False)
    tc.add_bm25_text(children)
    assert "bm25_text" not in children[0]
    monkeypatch.setattr(settings, "split_glued_ocr_words", True)
    tc.add_bm25_text(children)
    assert children[0]["bm25_text"] == "Now we shall discourse on the treatment"
    assert children[0]["text"] == "Nowweshalldiscourseonthetreatment"


def test_bm25_index_matches_on_bm25_text_but_returns_raw_text():
    from src.ingestion.bm25_store import build_bm25_index
    children = [
        {"chunk_id": "a", "text": "Nowweshalldiscourseonhaemorrhoids",
         "bm25_text": "Now we shall discourse on haemorrhoids", "metadata": {}},
        {"chunk_id": "b", "text": "fever and cough", "metadata": {}},
        {"chunk_id": "c", "text": "treatment of jaundice", "metadata": {}},
        {"chunk_id": "d", "text": "diet in fever", "metadata": {}},
    ]
    hits = build_bm25_index(children).search("haemorrhoids", top_n=1)
    assert hits[0]["chunk_id"] == "a"
    assert hits[0]["text"] == "Nowweshalldiscourseonhaemorrhoids"
