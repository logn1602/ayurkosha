"""Tests for src/ingestion/context_headers.py and its use in chunking / rerank.

Pages are synthetic but copy the markers the real corpus carries.

Run: python -m pytest tests/test_context_headers.py
"""

import pytest

from config.settings import settings
from src.ingestion.chunkers import chunk_record
from src.ingestion.context_headers import (afi_monograph_spans, afi_uses_lists, annotate_context,
                                            contextual_text, header_at)

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


def _after(rec, phrase):
    return header_at(rec["context"], rec["text"].index(phrase) + len(phrase))


def test_ss_garbled_openings_nidana_6_to_7_to_8():
    """Volume 2 glues and garbles its openings (pp. 98, 105, 110): each must still move
    the chapter on, even though the running heads in between are unreadable."""
    recs = annotate_context(_pages(SS, [
        "Chap.V.]NIDANASTHANAM.41 CHAPTER V. Now we shall discourse on the Nidanam of Kushtha",
        "CHAPTER-VI.Now^weshalldiscourseontheNiddnamofPrameha. Prameha is of twenty kinds",
        "cup.VL]SiDANASTHANAM.4}^non-relishforfood",                          # unreadable running head
        "CHAPTERVn.No\\yweshalldiscourseontheNidstnamofUdara. Udara is of eight kinds",
        "CHAPTERym.*Now*weshalldiscourseontheNiddnamofMudhagarbha. A dead foetus",
    ]))
    assert _after(recs[1], "Prameha") == f"{SS} > Nidanasthana, Chapter 6"
    assert _header_end(recs[2]) == f"{SS} > Nidanasthana, Chapter 6"
    assert _after(recs[3], "Udara") == f"{SS} > Nidanasthana, Chapter 7"
    assert _after(recs[4], "Mudhagarbha") == f"{SS} > Nidanasthana, Chapter 8"


def test_ss_garbled_opening_cikitsa_6_to_7():
    recs = annotate_context(_pages(SS, [
        "Chap.V.]CHIKITSASTHANAM.315 CHAPTERVI.NowweshalldiscourseonthemedicaltreatmentofHaemorrhoids",
        "Chap.VI.]CHIKITSASTHANAM.323 AmedicatedTakra",
        "CHAPTERVILNowwe»shalldiscourseonthemedicaltreatmentofAsmari(Urinarycalculus)",
    ]))
    assert _after(recs[0], "Haemorrhoids") == f"{SS} > Chikitsasthana, Chapter 6"
    assert _header_end(recs[1]) == f"{SS} > Chikitsasthana, Chapter 6"
    assert _after(recs[2], "Asmari") == f"{SS} > Chikitsasthana, Chapter 7"


@pytest.mark.parametrize("opening, chapter", [
    ("H A P T E R I v i I I . Now we shall discourse", 18),     # numeral unreadable: the next chapter
    ("CHAPTERXXXIIT.I^ow^weshalldiscourse", 18),                 # 33, far ahead: a misreading, the next chapter
    ("1 1 1 § L C H A P T E R X V I I I . Now shall discourse", 18),
])
def test_ss_an_opening_always_moves_the_chapter_on(opening, chapter):
    recs = annotate_context(_pages(SS, [
        "Chap. XVII.] UTTARA-TANTRA. 101 CHAPTER XVII. Now we shall discourse on the eye",
        opening + " on the treatment of the eye",
    ]))
    assert _after(recs[1], "the eye") == f"{SS} > Uttaratantra, Chapter {chapter}"


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
    # one heading split by OCR
    ("ksaya. 12:4 KASTURYADI (VAYU) GUTIKA (Sahasrayoga, Gutikaprakarana; 8.) text", "Kasturyadi (Vayu) Gutika"),
    ("agnimandya. 10:3 AROSOGHNi VATI (Siddhayogasangraha Arsodhikara) Nimbaphala (Sd.) 24 g.", "Arosoghni Vati"),
    # a garbled verse (second volume) right before its citation is not a title
    ("16:8 KANTAVALLABHA RASA ered VST APT fata | Waa eared ad Wg aaoda aH BOT II (Vasavarajiyam, "
     "Ksayaprakarana) Special Method of preparation", "Kantavallabha Rasa"),
    ("16:35 PRATAPALANKESVARA RASA Usgramdatdedaas ATT sam | WaATIA HaCaT Aaa: Fa: WAeht ESSCP ECE "
     "(Yogaratnakara; Strirogacikitsa; 868) Sdta (Suddha parada)", "Pratapalankesvara Rasa"),
    # ... but a numbered list entry after junk still is
    ("evaporate. APR wWN = 21. TUTTHA SODHANA (Rasamrta, Adhyaya 3; 74.) text", "Tuttha Sodhana"),
    ("16:3 AMRTA RASA sat diaatrared ara | wey seated SA Fat Aaled TINS Il\n(Bhaisajya ratnavali, "
     "Jvaratisaradhikara, 49-51)\nHingula", "Amrta Rasa"),                # a danda read as "Il"
    # a lowercase OCR slip inside a word, and a capital that starts the next word
    ("16:22 HEMAGARBHA POTTALi RASA\nqaqa waar fea", "Hemagarbha Pottali Rasa"),
    ("10:7. BOLADI VATi\n(Siddhayogasangraha, Strirogadhikara)\nHirabola", "Boladi Vati"),
    ("10:9 MAHASANKHA VATIi\nqgraafegare", "Mahasankha Vati"),
    ("18:1 ABHRAKA BHASMA Acceptable variety (A)", "Abhraka Bhasma"),
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


# ── Pharmacopoeia: no carry-forward past a monograph start ────────────

def test_api_garbled_running_header_falls_back_to_the_iast_title_line():
    recs = annotate_context(_pages(API, [
        "9. Yavani (Frt.)\nYAVĀNĪ (Fruit)\nYavānī consists of dried fruits of Trachyspermum ammi (Fam. Apiaceae)\n"
        "PROPERTIES AND ACTION",
        "1. Akarakarabha (R)t.)\nĀKĀRAKARABHA (Root)\nĀkārakarabha consists of dried roots of Anacyclus pyrethrum DC. "
        "(Fam.\nAsteraceae)",
    ]))
    assert _header_end(recs[0]).endswith("Yavani (Frt.)")
    assert _header_end(recs[1]) == f"{API} > Ākārakarabha (Root)"      # not "Yavani (Frt.)"


def test_api_opening_without_any_parsable_title_blanks_the_item():
    recs = annotate_context(_pages(API, [
        "9. Yavani (Frt.)\nYAVĀNĪ (Fruit)\nYavānī consists of dried fruits (Fam. Apiaceae)\nPROPERTIES AND ACTION",
        "#@ garbled heading line\nDroṇapuṣpī consists of dried whole plant of Leucas cephalotes Spreng. "
        "(Fam. Lamiaceae)",
    ]))
    assert _header_end(recs[1]) == API


def test_api_description_sentences_are_not_monograph_starts():
    recs = annotate_context(_pages(API, [
        "9. Yavani (Frt.)\nYAVĀNĪ (Fruit)\nYavānī consists of dried fruits (Fam. Apiaceae)\nDESCRIPTION",
        "Drug consists of small, ovoid fruit; mesocarp consists of polygonal parenchyma",
    ]))
    assert _header_end(recs[1]).endswith("Yavani (Frt.)")                # no false boundary


def test_api_plant_part_with_ampersand():
    recs = annotate_context(_pages(API, [
        "70. Tamalaki (Rt. St.& Lf.)\nTĀMALAKĪ (Root, Stem & Leaf)\nTāmalakī consists of root, stem and leaf "
        "of Phyllanthus urinaria (Fam. Euphorbiaceae)"]))
    assert _header_end(recs[0]) == f"{API} > Tamalaki (Rt. St.& Lf.)"


# ── Formulary spans for evidence sets: inclusive, unlike the headers ──

def _span_at(spans, page, offset):
    def key(pos):
        return (pos[0], float("inf") if pos[1] is None else pos[1])
    return next((s for s in spans if key(s["start"]) <= (page, offset) and (s["end"] is None or (page, offset) < key(s["end"]))),
                None)


def _rasnadi_pages(next_number="4:29", second_uses=""):
    return [
        "4:27 RASNADI KVATHA CURNA (Bhaisajyaratnavali, Amavatadhikara; 98-100.) 1. Rasna (Rt.) 1 part "
        "2. Eranda (Rt.) 1 part 3. Sunthi (Rz.) 1 part 4. Devadaru (Ht. Wd.) 1 part 5. Guduci (St.) 1 part "
        "6. Punarnava (Rt.) 1 part (Cakradatta, Amavatacikitsa; 58.) 7. Sati (Rz.) 1 part",
        "8. Vaca (Rz.) 1 part Dosage : 12 g. Important therapeutic uses : amavata; vataroga. " + second_uses +
        f"{next_number} RASNADI KVATHA CURNA (MAHA) (Sarngadharasamhita, Madhyamakhanda, Adhyaya 2; 90.) 1. Rasna",
    ]


def test_afi_misplaced_citation_does_not_split_a_formulation_from_its_uses_list():
    """The two-column layout moved a citation into the ingredient list. The header goes
    blank there (conservative: 4:28 may hide in between), but the formulation's span runs
    on to the next title, so its therapeutic-uses list on the next page stays with it."""
    pages = _rasnadi_pages()
    recs = annotate_context(_pages(AFI, pages))
    uses_at = pages[1].index("Important therapeutic uses")
    assert header_at(recs[1]["context"], uses_at) == AFI                 # header: blank after the citation
    spans = afi_monograph_spans(recs)
    assert [(s["number"], s["title"]) for s in spans] == [("4:27", "Rasnadi Kvatha Curna"),
                                                           ("4:29", "Rasnadi Kvatha Curna")]
    assert _span_at(spans, 2, uses_at) is spans[0]                        # span: the uses list is 4:27's
    assert spans[0]["end"] == (2, pages[1].index("4:29"))


def test_afi_blank_is_recovered_when_the_next_title_is_the_next_section_number():
    """4:27 then 4:28: nothing else can start in between, so the blank after the misplaced
    citation gets 4:27's name back."""
    pages = _rasnadi_pages("4:28")
    recs = annotate_context(_pages(AFI, pages))
    assert header_at(recs[1]["context"], pages[1].index("Important therapeutic uses")) == f"{AFI} > Rasnadi Kvatha Curna"


def test_afi_blank_stays_when_a_second_uses_list_shows_a_hidden_formulation():
    """Consecutive numbers, but two uses lists in between: a misread number or an
    untitled formulation hides there, so the blank stays."""
    pages = _rasnadi_pages("4:28", "%# garbled (Bhaisajyaratnavali, Vatavyadhyadhikara; 4.) 1. Bala (Rt.) 1 part "
                                   "Important therapeutic uses : pakshaghata. ")
    recs = annotate_context(_pages(AFI, pages))
    assert header_at(recs[1]["context"], pages[1].index("Important therapeutic uses")) == AFI


def test_afi_span_stops_before_the_next_groups_introduction():
    pages = [
        "5:12 SIMHANADA GUGGULU (Bhaisajyaratnavali, Amavatadhikara; 130-131.) 1. Triphala 3 parts "
        "Dosage : 3 g. Important therapeutic uses : amavata; vatarakta.",
        "GHRTA (SNEHAKALPA) Definition: Ghrtas are preparations in which ghee is boiled with kasayas.",
        "List of ghrtas: Kasisadi Ghrta, Jatyadi Ghrta (Bhaisajyaratnavali, Jvaradhikara) "
        "6:1 AMRTA GHRTA (Cakradatta, Amavatacikitsa; 58.) 1. Amrta (St.)",
    ]
    spans = afi_monograph_spans(annotate_context(_pages(AFI, pages)))
    assert spans[0]["title"] == "Simhanada Guggulu" and spans[0]["end"] == (1, None)   # ends with its page
    assert _span_at(spans, 2, 10) is None                                 # the group introduction is no one's


@pytest.mark.parametrize("next_title, end_page", [
    ("8:1 ASANA TAILA", 2),        # next group's first: the untitled 7:41 on page 2 is still group 7
    ("8:3 ASANABILVADI TAILA", 1),  # 8:1 and 8:2 unreadable too: page 2's list can't be assigned
])
def test_afi_span_at_a_group_change_keeps_only_lists_it_can_assign(next_title, end_page):
    pages = [
        "7:40 HUTABHUGADI CURNA (Bhaisajyaratnavali, Agnimandyadhikara; 12.) 1. Citraka (Rt.) 1 part "
        "Important therapeutic uses : agnimandya; pandu.",
        "%# unreadable title 1. Asana (St. Bk.) 1 part Important therapeutic uses : kustha; prameha.",
        "TAILA (SNEHAKALPA) Definition: Tailas are preparations in which oil is boiled with kasayas.",
        f"{next_title} (Sahasrayoga, Tailaprakarana; 45.) 1. Asana (St. Bk.) 1 part "
        "Important therapeutic uses : vatavyadhi.",
    ]
    spans = afi_monograph_spans(annotate_context(_pages(AFI, pages)))
    assert spans[0]["end"] == (end_page, None)
    assert _span_at(spans, 3, 10) is None                                 # never the introduction


def test_afi_uses_list_ignores_references_and_ingredient_names():
    text = ("Important therapeutic uses : 7. Kustha (Rt.) 8.7 g. amavata; sotha "
            "(Bhaisajyaratnavali, Jvaradhikara; 12-15) Dosage : 3 g.")
    [(offset, uses)] = afi_uses_lists(text)
    assert offset == text.index("therapeutic") and "amavata" in uses
    assert "Kustha" not in uses and "Jvara" not in uses                   # the herb, and the chapter name
