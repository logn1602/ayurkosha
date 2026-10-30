"""Tests for src/ingestion/context_headers.py and its use in chunking / rerank.

Pages are synthetic but copy the markers the real corpus carries.

Run: python -m pytest tests/test_context_headers.py
"""

import pytest

from config.settings import settings
from src.ingestion.chunkers import chunk_record
from src.ingestion.context_headers import annotate_context, contextual_text, header_at

API = "Ayurvedic Pharmacopoeia of India"
AFI = "Ayurvedic Formulary of India"
SS = "Sushruta Samhita"


def _pages(name, texts, source="doc.pdf"):
    return [{"text": t, "metadata": {"source": source, "page": i + 1, "text_name": name}}
            for i, t in enumerate(texts)]


def _header_end(record):
    return header_at(record["context"], len(record["text"]))


def test_api_herb_carries_across_pages_and_sections_follow():
    recs = annotate_context(_pages(API, [
        "10. Asvagandha (Rt.)\nAŚVAGANDHĀ (Root)\nconsists of dried roots\nSYNONYMS\nSanskrit : Hayagandhā",
        "b) Microscopic\nTransverse section of root\nPROPERTIES AND ACTION\nRasa : Tikta, Kaṣāya",
        "11. Atibala (Rt.)\nATIBALĀ (Root)\nconsists of root",
    ]))
    assert _header_end(recs[0]) == f"{API} > Synonyms > Asvagandha (Rt.)"
    assert _header_end(recs[1]) == f"{API} > Properties and Action > Asvagandha (Rt.)"
    assert _header_end(recs[2]) == f"{API} > Atibala (Rt.)"     # new monograph resets the section


def test_afi_formulation_and_group():
    recs = annotate_context(_pages(AFI, [
        "GROUP No. 5 GUGGULU 5:1 KANCANARA GUGGULU (Sarngadharasamhita) ingredients "
        "5:2 KAISORA GUGGULU (Bhaisajyaratnavali) 1. Guduci",
    ]))
    ctx = recs[0]["context"]
    assert header_at(ctx, 40) == f"{AFI} > Group 5: Guggulu > Kancanara Guggulu"
    assert header_at(ctx, len(recs[0]["text"])) == f"{AFI} > Group 5: Guggulu > Kaisora Guggulu"


def test_ss_chapters_survive_ocr_slips_crossrefs_and_contents():
    recs = annotate_context(_pages(SS, [
        "CONTENTS CHAPTERXL.Treatment of x. CHAPTERXLI.Treatment of y.",       # contents page
        "Chap.IX.]CHIKITSASTHANAM.361 text text",                              # running head
        "Chap.IX.]CHIKITSASTHANAM.362 as described in the Sutrasthana, see Chap. XXV text",
        "CHAPTERXL.Nowweshalldiscourseon the next chapter",                    # opening; "XL" is a misread XI
        "CH APTER XIl. Now we shall discourse on the following",                # spaced, l for I
        "Chap,XII.]CHIKITSASTHANAM.380 more",
    ]))
    assert _header_end(recs[0]) == SS                                          # contents ignored
    assert _header_end(recs[1]) == f"{SS} > Chikitsasthana, Chapter 9"
    assert _header_end(recs[2]) == f"{SS} > Chikitsasthana, Chapter 9"         # cross-refs ignored
    assert _header_end(recs[3]) == f"{SS} > Chikitsasthana, Chapter 11"        # L->I reading, nearest next (10)
    assert _header_end(recs[4]) == f"{SS} > Chikitsasthana, Chapter 12"
    assert _header_end(recs[5]) == f"{SS} > Chikitsasthana, Chapter 12"


def test_ss_new_sthana_restarts_chapters_even_with_chapter_first_running_head():
    recs = annotate_context(_pages(SS, [
        "Chap.XLVI.]SUTRASTHANAM.600 end of sutra",
        "Chap.I.]NIDANASTHANAM.1 Now",
    ]))
    assert _header_end(recs[1]) == f"{SS} > Nidanasthana, Chapter 1"


def test_chunk_headers_track_position_within_page():
    filler_a = " ".join(f"part{i} (Rt.) {i} g;" for i in range(60))
    filler_b = " ".join(f"item{i} (Fr.) {i} g;" for i in range(60))
    rec = annotate_context(_pages(AFI, [
        f"5:1 KANCANARA GUGGULU (Sarngadharasamhita) {filler_a} 5:2 KAISORA GUGGULU (Bhaisajyaratnavali) {filler_b}"
    ]))[0]
    children = chunk_record(rec)["children"]
    headers = [c["metadata"]["context_header"] for c in children]
    assert len(children) > 2
    assert headers[0].endswith("Kancanara Guggulu")
    assert headers[-1].endswith("Kaisora Guggulu")
    assert all("context_header" not in c for c in children)      # header lives in metadata, not text


def test_contextual_text_prepends_header_only_when_enabled(monkeypatch):
    chunk = {"text": "Rasa : Tikta", "metadata": {"context_header": f"{API} > Asvagandha (Rt.)"}}
    monkeypatch.setattr(settings, "contextual_chunk_headers", True)
    assert contextual_text(chunk) == f"{API} > Asvagandha (Rt.)\nRasa : Tikta"
    monkeypatch.setattr(settings, "contextual_chunk_headers", False)
    assert contextual_text(chunk) == "Rasa : Tikta"
    assert contextual_text({"text": "plain"}) == "plain"


def test_annotate_is_gated(monkeypatch):
    monkeypatch.setattr(settings, "contextual_chunk_headers", False)
    recs = annotate_context(_pages(API, ["10. Asvagandha (Rt.)\nx"]))
    assert "context" not in recs[0]
    assert "context_header" not in chunk_record(recs[0])["children"][0]["metadata"]


def test_rerank_sends_header_plus_text(monkeypatch):
    from types import SimpleNamespace
    from src.reranking import cohere_rerank as cr

    sent = {}

    class _Client:
        def rerank(self, query, documents, top_n, model):
            sent["docs"] = documents
            return SimpleNamespace(results=[SimpleNamespace(index=0, relevance_score=0.9)])

    monkeypatch.setattr(settings, "contextual_chunk_headers", True)
    monkeypatch.setattr(cr, "_get_client", lambda: _Client())
    out = cr.rerank("q", [{"chunk_id": "c", "text": "Rasa : Tikta",
                           "metadata": {"context_header": "API > Asvagandha (Rt.)"}}], top_n=1)
    assert sent["docs"] == ["API > Asvagandha (Rt.)\nRasa : Tikta"]
    assert out[0]["text"] == "Rasa : Tikta"                      # raw text kept for display


# ── Formulary titles: OCR variants seen in the corpus ─────────────────

@pytest.mark.parametrize("text, title", [
    # no "(" after the title (the old pattern required one)
    ("25. Vidari (Rt.Tr.) 48 g. 3:28 SIVA GUTIKA 26. Ksiravidari (Rt. Tr.) 48 g. 27. Vira (Rt.) 48 g. "
     "(Astangasangraha, Uttarasthana, Va", "Siva Gutika"),
    ("prameha; Slipada. 5:12 SIMHANADA GUGGULU _ (Bhaisajyaratnavali, Amavatadhikara; 130-131.) पलत्रयं",
     "Simhanada Guggulu"),
    ("44. Sukumara Ghrta Sahasrayoga, < Ghrtaprakarana 6:1 AMRTA GHRTA 1. Jivanti (Cakradatta, Amavatacikitsa; 58.)",
     "Amrta Ghrta"),
    ("Ot BESO ett Ne\n16:3 AMAVATARI RASA\nTat wet aa aay: erated: |\nuaewsdetst VET FT TIGA 11180",
     "Amavatari Rasa"),
    # spaced / semicolon numbers, and a number glued to the title
    ("kasa; Svasa. 1 : 9 KANAKASAVA (Bhaisajyaratnavali, Hikkasvasadhikara; 98-101)", "Kanakasava"),
    ("पिप्पलीं wer । 1 ; 14 KHADIRARISTA पर्पट मधुक रास्नां", "Khadirarista"),
    ("ksaya; daurbalya. 3:17PUGA KHANDA (Bhaisajyaratnavali, Sularogadhik", "Puga Khanda"),
    # garbled number: the title is found by its source reference
    ("fe LASUNADI GHRTA (Astangahrdaya, Cikitsasthana, Adhyaya 14; 22-25.) तुला", "Lasunadi Ghrta"),
])
def test_afi_titles_found_in_ocr_variants(text, title):
    rec = annotate_context(_pages(AFI, [text]))[0]
    assert header_at(rec["context"], len(text)) == f"{AFI} > {title}"


def test_afi_unparseable_monograph_start_blanks_the_item():
    """A source reference with no readable title before it starts a new monograph: the
    previous name must not carry on (a wrong header is worse than none)."""
    recs = annotate_context(_pages(AFI, [
        "5:12 SIMHANADA GUGGULU (Bhaisajyaratnavali, Amavatadhikara; 130-131.) 1. Triphala 3 parts",
        "% ^ 17 ¢ (Bhaisajyaratnavali, Murccha ra; 13-17) 28. Maksika (madhu) 2.400 kg.",
        "Dosage : 12 to 24 ml. Important therapeutic uses : murccha.",
    ]))
    assert _header_end(recs[0]) == f"{AFI} > Simhanada Guggulu"
    assert _header_end(recs[1]) == AFI          # blank from the stranded reference on
    assert _header_end(recs[2]) == AFI          # ... and not revived on later pages
