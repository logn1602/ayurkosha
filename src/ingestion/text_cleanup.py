"""
AyurKosha — Corpus Text Cleanup
Repairs text-layer defects in the source PDFs before chunking.

1. Legacy-font character mapping (``fix_font_artifacts``)
   The Ayurvedic Pharmacopoeia PDF stores IAST diacritics in an old 8-bit
   font, so its text layer reads "A¿vagandh¡" for Aśvagandhā and "V¢rya" for
   Vīrya. Sushruta's and Ashtanga Hridaya's English OCR misreads ā as "£"
   ("V£yu", "vid£rigandha"). The tables below were derived from the corpus: an
   inventory of every non-ASCII, non-Devanagari character by frequency, with
   sample contexts (see docs/corpus_text_fixes.md). Mappings are scoped per
   work, because the same byte means different things in different books
   (£ is ū in the Pharmacopoeia but ā in the classical OCR).

   PROPOSED, not yet confirmed: applied only when
   ``settings.apply_font_char_map`` is True.

2. Diacritic folding for BM25 (``fold_diacritics``)
   The BM25 tokenizer keeps only [a-z0-9] runs, so "Aśvagandhā" would split
   into "a"/"vagandh". Folding (ś→s, ā→a) keeps IAST words whole. Gated by
   ``settings.bm25_fold_diacritics``; enable it together with the char map.

Build this in: Phase 7 (corpus quality)
"""

from __future__ import annotations

import re
import unicodedata

from config.settings import settings
from src.ingestion.metadata import infer_text_name

# ── 1. Legacy-font character maps ─────────────────────────────────────
# char -> replacement. Comments give corpus counts and an example.

# Ayurvedic Pharmacopoeia of India — high confidence: each mapping is
# confirmed by many words that decode to known IAST spellings.
API_CHAR_MAP: dict[str, str] = {
    "¡": "ā",  # ¡  6357  Vip¡ka -> Vipāka
    "À": "ṣ",  # À  2603  UÀ¸a -> Uṣṇa
    "¸": "ṇ",  # ¸  2409  Gu¸a -> Guṇa
    "¢": "ī",  # ¢  2394  V¢rya -> Vīrya
    "£": "ū",  # £  1417  R£kÀa -> Rūkṣa
    "¶": "ṭ",  # ¶  1369  Ka¶u -> Kaṭu
    "á": "Ś",  # á  1251  á¢ta -> Śīta, AáOKA -> AŚOKA
    "¤": "ṛ",  # ¤  1242  Gh¤ta -> Ghṛta
    "¿": "ś",  # ¿   997  A¿vagandh¡ -> Aśvagandhā
    "·": "ḍ",  # ·   362  P¡¸·u -> Pāṇḍu
    "´": "ṅ",  # ´   197  A´gamarda -> Aṅgamarda
    "Æ": "ṃ",  # Æ   158  B¤Æha¸a -> Bṛṃhaṇa
    "Å": "ḥ",  # Å   120  áiraÅ -> Śiraḥ
    "®": "e",  # ®    ~20 T®j°vati -> Tejovati, D®vak¡Àtha -> Devakāṣṭha (medium)
    # Upper case, used in monograph titles.
    "Ë": "Ā",  # Ë   730  AJAGANDHË -> AJAGANDHĀ
    "Ì": "Ī",  # Ì   313  ËMALAKÌ -> ĀMALAKĪ
    "â": "Ṣ",  # â   107  GOKâURA -> GOKṢURA
    "Í": "Ū",  # Í    99  BABBÍLA -> BABBŪLA
    "Û": "Ṇ",  # Û    96  ERAÛÚA -> ERAṆḌA
    "Ù": "Ṭ",  # Ù    74  KUâÙHA -> KUṢṬHA
    "Ú": "Ḍ",  # Ú    50  GUÚÍCÌ -> GUḌŪCĪ
    "×": "Ṅ",  # ×    49  VIÚA×GA -> VIḌAṄGA
    "Î": "Ṛ",  # Î    42  KÎâÛAJÌRAKA -> KṚṢṆAJĪRAKA
    "Ø": "Ñ",  # Ø    31  GUØJË -> GUÑJĀ
    "ê": "Ṃ",  # ê    14  HAêSAPADÌ -> HAṂSAPADĪ
    "é": "Ḥ",  # é    41  PALĀŚAé -> PALĀŚAḤ (title visarga; found on re-inventory, medium)
    # Low confidence (1–2 occurrences each); mapped from a single decoded word.
    "Ó": "E",  # Ó     2  RÓÛUKA -> REṆUKA
    "½": "l",  # ½     1  N¡rik®½a -> Nārikela
}
# Context-sensitive: real symbols in the Pharmacopoeia unless between letters.
#   µ  831: "µ" / "µm" is micron; Karaµja -> Karañja, Paµca -> Pañca
#   °  206: "105°C" is degrees; L°hitapuÀpa -> Lohitapuṣpa, á°dhana -> Śodhana
_API_INFIX = {"µ": "ñ", "°": "o"}
_API_INFIX_RE = re.compile(r"(?<=[^\W\d_])([µ°])(?=[^\W\d_])")
_API_MICRON_RE = re.compile("ƒÊ")  # "ƒÊm" (2) is a garbled "µm"

# Sushruta Samhita / Ashtanga Hridaya English OCR — medium confidence.
CLASSICAL_OCR_CHAR_MAP: dict[str, str] = {
    "£": "ā",  # £  SS/AH ~600 (in words)  V£yu -> Vāyu, vid£rigandha -> vidārigandha
}
_IN_WORD_POUND_RE = re.compile(r"(?<=[A-Za-z])£|£(?=[a-z])")
# Soft hyphen left by OCR line-break hyphenation: "our\xad selves" -> "ourselves".
_SOFT_HYPHEN_RE = re.compile("­\\s*")

# Ayurvedic Formulary of India — otherwise ASCII-transliterated; its one
# systematic artifact is the gram unit read as "£" after a quantity
# (430 of 465 cases): "bibhitaka (p.) 24 £." -> "24 g.". Medium confidence.
_AFI_GRAM_RE = re.compile(r"(?<=\d)(\s*)£")

_API = "Ayurvedic Pharmacopoeia of India"
_AFI = "Ayurvedic Formulary of India"
_CLASSICAL_OCR = {"Sushruta Samhita", "Ashtanga Hridaya"}


def fix_font_artifacts(text: str, text_name: str | None) -> str:
    """Map legacy-font / OCR characters to IAST for one work's text.

    Args:
        text: Page text.
        text_name: Canonical work title (metadata ``text_name``); selects the map.

    Returns:
        The repaired text, or ``text`` unchanged for works without a map.
    """
    if not text:
        return text
    if text_name == _API:
        text = _API_MICRON_RE.sub("µ", text)
        text = _API_INFIX_RE.sub(lambda m: _API_INFIX[m.group(1)], text)
        return text.translate(str.maketrans(API_CHAR_MAP))
    if text_name == _AFI:
        return _AFI_GRAM_RE.sub(lambda m: m.group(1) + "g", text)
    if text_name in _CLASSICAL_OCR:
        text = _SOFT_HYPHEN_RE.sub("", text)
        return _IN_WORD_POUND_RE.sub(CLASSICAL_OCR_CHAR_MAP["£"], text)
    return text


def apply_font_fixes(records: list[dict]) -> list[dict]:
    """Repair page records in place when ``settings.apply_font_char_map`` is on.

    Runs before metadata enrichment, so the work is inferred from ``source``.
    """
    if not settings.apply_font_char_map:
        return records
    for record in records:
        meta = record.get("metadata", {})
        name = meta.get("text_name") or infer_text_name(meta.get("source", ""))
        record["text"] = fix_font_artifacts(record.get("text", ""), name)
    return records


# ── 2. Diacritic folding ──────────────────────────────────────────────

def _fold_char(ch: str) -> str:
    if ch.isascii() or "ऀ" <= ch <= "ॿ":   # Devanagari matras are combining marks too
        return ch
    return "".join(c for c in unicodedata.normalize("NFKD", ch) if not unicodedata.combining(c))


def fold_diacritics(text: str) -> str:
    """Strip Latin diacritics ("Aśvagandhā" -> "Asvagandha"); Devanagari is untouched."""
    if text.isascii():
        return text
    return "".join(_fold_char(ch) for ch in text)
