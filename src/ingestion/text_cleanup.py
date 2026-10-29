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


# ── 3. Run-together OCR word splitting (BM25 text only) ───────────────
# Sushruta vol 1-2 OCR dropped most spaces: 83-85% of their Latin text sits
# in letter runs of 15+ chars ("thedrugsknownasapamargaashvagandha"), which
# BM25 can't match. wordninja splits such runs by word-frequency DP, but its
# list is English-only and would chop Sanskrit ("ash va gandha"). So the
# language model is English + a *protected vocabulary* learned from the
# corpus's properly spaced sources, and a run is split only when every piece
# is a known word.

GLUE_MIN_RUN = 15            # letter runs at least this long are split candidates
GLUED_SOURCE_RATIO = 0.05    # sources with more glued runs than this don't teach vocab
_PROTECTED_MIN_FREQ = 3
_LETTER_RUN_RE = re.compile(r"[A-Za-z]+")


def glued_run_ratio(texts) -> float:
    """Fraction of letter runs that are GLUE_MIN_RUN+ chars long."""
    total = glued = 0
    for text in texts:
        for run in _LETTER_RUN_RE.findall(fold_diacritics(text)):
            total += 1
            glued += len(run) >= GLUE_MIN_RUN
    return glued / total if total else 0.0


def build_protected_vocab(texts_by_source: dict[str, list[str]],
                          extra_words=()) -> dict[str, int]:
    """Word -> corpus frequency, learned from sources that are properly spaced.

    Sources whose glued-run ratio exceeds GLUED_SOURCE_RATIO are skipped, so
    glued fragments ("andthe") never become "words". ``extra_words`` (e.g.
    synonym-dictionary names) are always included.
    """
    counts: dict[str, int] = {}
    for source, texts in texts_by_source.items():
        if glued_run_ratio(texts) > GLUED_SOURCE_RATIO:
            continue
        for text in texts:
            for run in _LETTER_RUN_RE.findall(fold_diacritics(text).lower()):
                if 3 <= len(run) < GLUE_MIN_RUN:
                    counts[run] = counts.get(run, 0) + 1
    vocab = {w: n for w, n in counts.items() if n >= _PROTECTED_MIN_FREQ}
    for word in extra_words:
        for run in _LETTER_RUN_RE.findall(fold_diacritics(word).lower()):
            if len(run) >= 3:
                vocab[run] = max(vocab.get(run, 0), _PROTECTED_MIN_FREQ)
    return vocab


class GluedWordSplitter:
    """Splits run-together letter runs using English + protected corpus vocab.

    Pieces the model isn't confident about (not in the vocabulary, or a short
    piece that isn't a common short word) are glued back to their unknown
    neighbours, so an unrecognized Sanskrit or OCR-garbled name stays whole
    ("Prithak" rather than "Pr it hak"). A run is split only when known words
    cover at least SPLIT_MIN_KNOWN of it.
    """

    SPLIT_MIN_KNOWN = 0.6
    MIN_CANDIDATE_RUN = 8        # shorter runs are left alone
    _SHORT = 3                   # pieces this short need to be common words
    # Never absorbed into an unknown neighbour; may open a capitalized word.
    FUNCTION_WORDS = frozenset(
        "a an and are as at be by for from has he his i in is it its of on or "
        "that the their this to was were which with".split())
    # May be peeled off the end of a capitalized word ("Indivaraand").
    TRAILING_WORDS = frozenset("and are etc for from has its the their this was were which with".split())
    _CAMEL_RE = re.compile(r"(?<=[a-z])(?=[A-Z])")

    def __init__(self, protected_vocab: dict[str, int]):
        import gzip
        import math
        import os

        import wordninja

        path = os.path.join(os.path.dirname(wordninja.__file__), "wordninja", "wordninja_words.txt.gz")
        with gzip.open(path) as f:
            english = f.read().decode().split()
        # Rank = position in the merged frequency order; an English word keeps
        # its rank, a corpus word ranks by its corpus frequency, and the better
        # (lower) rank wins. Zipf cost as in wordninja.
        rank = {w: i for i, w in enumerate(english)}
        for i, w in enumerate(sorted(protected_vocab, key=lambda w: -protected_vocab[w])):
            rank[w] = min(rank.get(w, i), i)
        n = len(rank)
        self._known = set(english[:100_000]) | set(protected_vocab)
        self._short_ok = ({w for w in english[:2000] if len(w) <= self._SHORT}
                          | {w for w, c in protected_vocab.items() if len(w) <= self._SHORT and c >= 50})
        self._model = wordninja.LanguageModel.__new__(wordninja.LanguageModel)
        self._model._wordcost = {w: math.log((r + 1) * math.log(n)) for w, r in rank.items()}
        self._model._maxword = max(len(w) for w in rank)

    def _confident(self, piece: str) -> bool:
        low = piece.lower()
        if len(low) <= self._SHORT:
            return low in self._short_ok
        return low in self._known

    def split_run(self, run: str) -> str:
        """Split one letter run, or return it unchanged if not confidently splittable.

        The run is first cut at lower->Upper boundaries ("theKakolyadi" ->
        "the" + "Kakolyadi"): the translation capitalizes Sanskrit names, so a
        case change marks a word start.
        """
        return " ".join(self._split_segment(seg) for seg in self._CAMEL_RE.split(run))

    def _split_segment(self, seg: str) -> str:
        if len(seg) < self.MIN_CANDIDATE_RUN or seg.lower() in self._known:
            return seg
        pieces = list(self._model._split(seg))
        if len(pieces) < 2:
            return seg
        # A short capitalized word is usually a Sanskrit name ("Pindaluka"):
        # split it only when it opens with a glued function word ("Amedicated").
        if seg[0].isupper() and len(seg) < GLUE_MIN_RUN:
            if pieces[0].lower() in self.FUNCTION_WORDS and all(map(self._confident, pieces)):
                return " ".join(pieces)
            if pieces[-1].lower() in self.TRAILING_WORDS and len(seg) - len(pieces[-1]) >= 4:
                return seg[:-len(pieces[-1])] + " " + pieces[-1]
            return seg
        unknown = [not self._confident(p) for p in pieces]
        # Short non-function pieces touching an unknown piece are fragments of it.
        changed = True
        while changed:
            changed = False
            for i, p in enumerate(pieces):
                if (not unknown[i] and len(p) <= self._SHORT and p.lower() not in self.FUNCTION_WORDS
                        and ((i > 0 and unknown[i - 1]) or (i + 1 < len(pieces) and unknown[i + 1]))):
                    unknown[i] = changed = True
        merged: list[str] = []
        merged_unknown: list[bool] = []
        for p, u in zip(pieces, unknown):
            if merged and (u and merged_unknown[-1] or (u and len(p) <= 2 and p.lower() not in ("a", "i"))):
                merged[-1] += p                    # extend an unknown span / re-attach a stray suffix
                merged_unknown[-1] = merged_unknown[-1] and u
            else:
                merged.append(p)
                merged_unknown.append(u)
        known_chars = sum(len(p) for p, u in zip(merged, merged_unknown) if not u)
        unknown_spans = [p for p, u in zip(merged, merged_unknown) if u]
        # One unknown, word-sized span among confident words is still a good
        # split ("alleviate" + "haemoptysis").
        one_word_gap = len(unknown_spans) == 1 and len(unknown_spans[0]) >= 5
        if len(merged) < 2 or (known_chars / len(seg) < self.SPLIT_MIN_KNOWN and not one_word_gap):
            return seg
        return " ".join(merged)

    def split(self, text: str) -> str:
        """Split every glued run in ``text`` (diacritics folded first)."""
        return _LETTER_RUN_RE.sub(lambda m: self.split_run(m.group()), fold_diacritics(text))


def add_bm25_text(children: list[dict]) -> list[dict]:
    """Attach a glue-split ``bm25_text`` to each child when enabled.

    The protected vocabulary is learned from this same batch of children
    (grouped by source) plus the synonym dictionaries, so it always matches
    the corpus being indexed. ``text`` itself is left untouched.
    """
    if not settings.split_glued_ocr_words or not children:
        return children
    from src.ingestion.synonym_loader import load_synonym_index

    by_source: dict[str, list[str]] = {}
    for child in children:
        by_source.setdefault(child.get("metadata", {}).get("source", ""), []).append(child.get("text", ""))
    synonyms = {v for variants in load_synonym_index().values() for v in variants}
    splitter = GluedWordSplitter(build_protected_vocab(by_source, extra_words=sorted(synonyms)))
    for child in children:
        child["bm25_text"] = splitter.split(child.get("text", ""))
    return children
