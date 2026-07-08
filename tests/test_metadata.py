"""Tests for src/ingestion/metadata.py (synthetic fixtures).

Run: python -m pytest tests/test_metadata.py
"""

from src.ingestion.metadata import (
    infer_text_name,
    extract_chapter,
    extract_sthana,
    extract_headings,
    extract_properties,
    detect_monograph_sections,
    build_citation,
    enrich_record,
)


# ── text_name inference ───────────────────────────────────────────────

def test_infer_text_name_classical():
    assert infer_text_name("charaka_samhita_pv_sharma.pdf") == "Charaka Samhita"
    assert infer_text_name("sushruta_samhita_vol_1.pdf") == "Sushruta Samhita"
    assert infer_text_name("ashtanga_hridaya_illustrated.pdf") == "Ashtanga Hridaya"


def test_infer_text_name_pharmacopoeia():
    assert infer_text_name("api_all_volume.pdf") == "Ayurvedic Pharmacopoeia of India"
    assert infer_text_name("afi_part1.pdf") == "Ayurvedic Formulary of India"


def test_infer_text_name_unknown():
    assert infer_text_name("random_notes.pdf") is None


# ── chapter / sthana ──────────────────────────────────────────────────

def test_extract_chapter_roman():
    assert extract_chapter("Chap.XXV.] SUTRASTHANAM 245") == "25"


def test_extract_chapter_arabic():
    assert extract_chapter("Chikitsa Sthana, Chapter 3, Jwara") == "3"


def test_extract_chapter_none():
    assert extract_chapter("no chapter marker here") is None


def test_extract_sthana_variants():
    assert extract_sthana("... SUTRASTHANAM ...") == "Sutrasthana"
    assert extract_sthana("Charaka, Chikitsasthana") == "Chikitsasthana"
    assert extract_sthana("Sarirasthana section") == "Sharirasthana"


def test_extract_sthana_none():
    assert extract_sthana("plain english paragraph") is None


# ── headings / monograph structure ────────────────────────────────────

def test_extract_headings():
    text = "SYNONYMS\nsome text\nDESCRIPTION\nmore text\nlowercase line"
    heads = extract_headings(text)
    assert "SYNONYMS" in heads
    assert "DESCRIPTION" in heads
    assert "lowercase line" not in heads


def test_detect_monograph_sections():
    text = "SYNONYMS\n...\nPROPERTIES AND ACTION\n...\nTHERAPEUTIC USES\n..."
    secs = detect_monograph_sections(text)
    assert "SYNONYMS" in secs
    assert "PROPERTIES AND ACTION" in secs
    assert "THERAPEUTIC USES" in secs


def test_extract_properties():
    text = "Rasa : Katu, Tikta\nGuna : Laghu\nVirya : Ushna\nKarma : Dipana"
    props = extract_properties(text)
    assert props["rasa"] == "Katu, Tikta"
    assert props["guna"] == "Laghu"
    assert props["virya"] == "Ushna"
    assert props["karma"] == "Dipana"


def test_extract_properties_absent():
    assert extract_properties("no properties in this text") == {}


# ── citation building ─────────────────────────────────────────────────

def test_build_citation_full():
    meta = {"text_name": "Charaka Samhita", "sthana": "Chikitsasthana",
            "chapter": "3", "page": 415}
    assert build_citation(meta) == "Charaka Samhita, Chikitsasthana, Chapter 3, p. 415"


def test_build_citation_requires_text_name():
    assert build_citation({"sthana": "Sutrasthana"}) is None


# ── enrich_record end-to-end ──────────────────────────────────────────

def test_enrich_classical_record():
    rec = {
        "text": "Chap.III.] CHIKITSASTHANAM. Treatment of Jwara ...",
        "metadata": {"source": "charaka_samhita_pv_sharma.pdf",
                     "doc_type": "classical_text", "page": 415},
    }
    enrich_record(rec)
    m = rec["metadata"]
    assert m["text_name"] == "Charaka Samhita"
    assert m["sthana"] == "Chikitsasthana"
    assert m["chapter"] == "3"
    assert m["citation"].startswith("Charaka Samhita, Chikitsasthana, Chapter 3")


def test_enrich_pharmacopoeia_record():
    rec = {
        "text": "SYNONYMS\nAmalaki\nPROPERTIES AND ACTION\nRasa : Amla\nKarma : Rasayana",
        "metadata": {"source": "api_all_volume.pdf",
                     "doc_type": "pharmacopoeia", "page": 44},
    }
    enrich_record(rec)
    m = rec["metadata"]
    assert m["is_monograph"] is True
    assert "SYNONYMS" in m["monograph_sections"]
    assert m["rasa"] == "Amla"
    assert m["karma"] == "Rasayana"
    assert m["text_name"] == "Ayurvedic Pharmacopoeia of India"
