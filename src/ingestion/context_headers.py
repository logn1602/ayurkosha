"""
AyurKosha — Contextual Chunk Headers
Gives every child chunk a header naming where it sits in its work:

    "[Work] > [Section/Chapter] > [Herb/Formulation]"
    e.g. "Ayurvedic Pharmacopoeia of India > Properties and Action > Asvagandha (Rt.)"

A 450-char child often lacks the very words that identify it: a Pharmacopoeia
"Rasa : Tikta…" block never names its herb, and that name is on the
monograph's first page. The header is prepended to the text used for
**embedding and reranking** (``contextual_text``). The raw ``text`` is kept
as-is for display and citations, and the header is stored separately in
``metadata["context_header"]``.

Structure is read per work from the markers its pages actually carry:
  - Pharmacopoeia: "10. Asvagandha (Rt.)" opens a monograph; section headings
    (PROPERTIES AND ACTION, …) follow within it.
  - Formulary: "5:2 KAISORA GUGGULU (Bhaisajyaratnavali…)" opens a
    formulation; "GROUP No. 5 GUGGULU" opens a section.
  - Sushruta: "Chap. IX.] CHIKITSASTHANAM" running heads / "CHAPTER XLIV."
  - Ashtanga Hridaya (English): "Dinacarya Adhyaya : 2" running heads and
    "Amalaki (Emblica officinalis):" drug entries.
Items and sections carry forward across pages until the next marker, so a
chunk on page 3 of a monograph still knows its herb.

Gated by ``settings.contextual_chunk_headers``. Takes effect on the next
ingestion.

Build this in: Phase 7 (retrieval quality)
"""

from __future__ import annotations

import re
from typing import Any

from config.settings import settings
from src.ingestion.metadata import MONOGRAPH_SECTION_HEADERS, _roman_to_int

# ── Markers per work ──────────────────────────────────────────────────
_API_MONOGRAPH_RE = re.compile(r"^\s*\d{1,3}\.\s+([A-Z][A-Za-z\- ]{2,40}?)\s*\(([A-Za-z. \-]{2,25})\)\s*$", re.M)
_AFI_ITEM_RE = re.compile(r"\b\d{1,2}:\d{1,3}\s+([A-Z][A-Z()\-' ]{2,60}?)\s*\(")
_AFI_GROUP_RE = re.compile(r"\bGROUP\s+No\.?\s*(\d{1,2})\s*[—-]*\s*([A-Z][A-Z\-]+(?:\s[A-Z][A-Z\-]+)?)")
_SS_CHAPTER_RE = re.compile(r"\bCHAP(?:TER|[.,])?\s*([IVXLC]{1,8})\b\.?", re.I)   # "Chap,VI." occurs too
# Only a *heading* ("CHAPTER XLIV.", "CHIKITSASTHANAM") or the running head
# at the top of a page ("Chap.IX.]CHIKITSASTHANAM", "...] UTTARA-TANTRA 367")
# counts; "see Chap. X" or "described in the Sutrasthana" in the body is a
# cross-reference.
_SS_RUNNING_HEAD_CHARS = 80
# Every Sushruta chapter opens "CHAPTER <n>. Now we shall discourse on…". The
# OCR letter-spaces the heading ("C H A P T E R X L .", "CH APTER", "CHAPER")
# and substitutes numeral glyphs (Y=V, H=II, 1/l=I), so the opening sentence is
# the reliable anchor.
_SS_OPENING_RE = re.compile(
    r"C\s?H\s?A\s?P\s?T?\s?E\s?R\s*,?\s*([IVXLYH1l](?:\s?[IVXLYH1l]){0,9})\s*\.*\s*N\s*o\s*w\s*w\s*e\s*s\s*h\s*a\s*l\s*l")
_CONTENTS_MIN_HEADINGS = 2    # uppercase CHAPTER mentions on a page with no chapter opening
_OCR_NUMERAL = str.maketrans({"Y": "V", "1": "I", "l": "I", " ": None})
_SS_STHANA_RE = re.compile(
    r"(SUTRA|NIDANA|SHARIRA|SARIRA|CHIKITSA|CHIKITSITA|KALPA)\s*-?\s*STHANA|U\s*T\s*T\s*A\s*R\s*A\s*-?\s*T\s*A\s*N\s*T\s*R\s*A",
    re.I)
_AH_ADHYAYA_RE = re.compile(r"([A-Z][A-Za-z\-]+(?: [A-Z][A-Za-z\-]+){0,3})\s+Adhyaya\s*:\s*(\d{1,2})\b")
_AH_STHANA_RE = re.compile(r"(Sutra|Sarira|Sharira|Nidana|Cikitsa|Kalpa|Uttara)\s*-?\s*sthana", re.I)
_AH_DRUG_RE = re.compile(r"^\s*([A-Z][a-z]{2,20}(?: [a-z]{2,15})?)\s*\(([A-Z][A-Za-z .]{3,40})\)\s*:", re.M)

_STHANA_NAMES = {"sutra": "Sutrasthana", "nidana": "Nidanasthana", "sharira": "Sharirasthana",
                 "sarira": "Sharirasthana", "chikitsa": "Chikitsasthana", "chikitsita": "Chikitsasthana",
                 "cikitsa": "Chikitsasthana", "kalpa": "Kalpasthana", "uttara": "Uttaratantra"}
_SECTION_HEADER_RE = re.compile(
    r"^\s*(" + "|".join(re.escape(h) for h in sorted(MONOGRAPH_SECTION_HEADERS, key=len, reverse=True)) + r")\b",
    re.M)


_MINOR_WORDS = {"and", "of", "the", "in", "for", "with"}


def _title(s: str) -> str:
    words = [w.capitalize() if w.isupper() else w for w in s.split()]
    return " ".join(w.lower() if i and w.lower() in _MINOR_WORDS else w for i, w in enumerate(words))


def _sthana(match_text: str) -> str:
    key = re.sub(r"[^a-z]", "", match_text.lower())
    for prefix, name in _STHANA_NAMES.items():
        if key.startswith(prefix):
            return name
    return _title(match_text)


def _marks(text: str, text_name: str | None) -> tuple[list[tuple[int, str]], list[tuple[int, str]]]:
    """(section_marks, item_marks): (offset, label) lists for one page."""
    sections: list[tuple[int, str]] = []
    items: list[tuple[int, str]] = []
    if text_name == "Ayurvedic Pharmacopoeia of India":
        items = [(m.start(), f"{m.group(1).strip()} ({m.group(2).strip()})") for m in _API_MONOGRAPH_RE.finditer(text)]
        sections = [(m.start(), _title(m.group(1))) for m in _SECTION_HEADER_RE.finditer(text)]
        # A new monograph resets the section until its first heading.
        sections += [(off, "") for off, _ in items]
    elif text_name == "Ayurvedic Formulary of India":
        items = [(m.start(), _title(m.group(1).strip())) for m in _AFI_ITEM_RE.finditer(text)]
        sections = [(m.start(), f"Group {int(m.group(1))}: {_title(m.group(2))}") for m in _AFI_GROUP_RE.finditer(text)]
    elif text_name == "Sushruta Samhita":
        # Running heads print the sthana in capitals; mixed case is body text.
        sthanas = [(m.start(), _sthana(m.group(0))) for m in _SS_STHANA_RE.finditer(text) if m.group(0).isupper()]
        # Chapter openings ("CHAPTER XLIV. Now we shall discourse…") are the
        # strong signal; otherwise only the running head at the top of a page.
        openings = [(m.start(), (m.group(1).translate(_OCR_NUMERAL).replace("H", "II"), True))
                    for m in _SS_OPENING_RE.finditer(text)]
        mentions = list(_SS_CHAPTER_RE.finditer(text))
        if not openings and sum(m.group(0).isupper() for m in mentions) >= _CONTENTS_MIN_HEADINGS:
            return [], []          # a table-of-contents page: its headings aren't the text's structure
        # OCR reads I as lowercase l ("CHAPTERXVIIl.", "Chap.Vlll."); l is never a numeral here.
        heads = [(m.start(), (m.group(1).replace("l", "I").upper(), False)) for m in mentions
                 if m.start() < _SS_RUNNING_HEAD_CHARS and not any(abs(m.start() - o) < 25 for o, _ in openings)]
        sections = ([(off, ("sthana", s)) for off, s in sthanas]
                    + [(off, ("chapter_raw", c)) for off, c in openings + heads])
    elif text_name == "Ashtanga Hridaya":
        sections = [(m.start(), ("adhyaya", f"{_title(m.group(1))} Adhyaya ({int(m.group(2))})"))
                    for m in _AH_ADHYAYA_RE.finditer(text)]
        sections += [(m.start(), ("sthana", _sthana(m.group(1)))) for m in _AH_STHANA_RE.finditer(text)]
        items = [(m.start(), f"{m.group(1).strip()} ({m.group(2).strip()})") for m in _AH_DRUG_RE.finditer(text)]
    return sorted(sections, key=lambda x: x[0]), sorted(items, key=lambda x: x[0])


def annotate_context(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Attach ``record["context"]`` (markers + carried-in state) to page records.

    Records must be in reading order per source (as loaders produce them).
    Sushruta / AH sections are composite ("Chikitsasthana, Chapter 9"): the
    sthana and chapter parts are carried independently.
    """
    if not settings.contextual_chunk_headers:
        return records
    carry: dict[str, dict[str, Any]] = {}
    for record in records:
        meta = record.get("metadata", {})
        source, name = meta.get("source", ""), meta.get("text_name")
        state = carry.setdefault(source, {"section": "", "parts": {}, "item": ""})
        sections, items = _marks(record.get("text", ""), name)
        sections = _resolve_chapters(sections, state["parts"])
        record["context"] = {"work": name or "", "section_in": state["section"], "parts_in": dict(state["parts"]),
                             "item_in": state["item"], "sections": sections, "items": items}
        for _, label in sections:
            state["section"] = _apply_section(state["parts"], label)
        if items:
            state["item"] = items[-1][1]
    return records


_CHAPTER_MAX_STEP = 3
_ROMAN_VALUES = [(100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]


def _canonical_roman(numeral: str) -> int | None:
    """Value of a *canonical* roman numeral (round-trips), else None ("XVIIL" -> None)."""
    n = _roman_to_int(numeral)
    if not n:
        return None
    out, rest = "", n
    for value, sym in _ROMAN_VALUES:
        while rest >= value:
            out, rest = out + sym, rest - value
    return n if out == numeral else None


def _resolve_chapters(sections: list, parts: dict[str, Any]) -> list:
    """Turn raw OCR'd chapter numerals into accepted ("chapter", n) marks.

    Chapters only move forward within a sthana. A running-head numeral is
    accepted when it lies 0..3 chapters ahead of the current one; a chapter
    opening ("CHAPTER n. Now we shall discourse…") may jump any distance
    forward (headings lost to OCR leave gaps) but never back. Both readings
    of an OCR slip are tried (as read, and L->I: "XXXILI" -> XXXIII, "XL" ->
    XI) and the valid one nearest the next expected chapter wins. Truncated
    running heads ("Chap. X" for XXXIX) and cross-references are dropped.

    A sthana change on the page clears the chapter (numbering restarts), and
    is moved to the top of the page so it applies before that page's chapter
    marks: the running head prints "Chap.I.]NIDANASTHANAM", chapter first.
    """
    current = parts.get("chapter")
    page_sthanas = [label[1] for _, label in sections if isinstance(label, tuple) and label[0] == "sthana"]
    resolved = []
    if page_sthanas and page_sthanas[0] != parts.get("sthana"):
        current = None
        resolved.append((0, ("sthana_change", page_sthanas[0])))
    for off, label in sections:
        if not (isinstance(label, tuple) and label[0] == "chapter_raw"):
            resolved.append((off, label))
            continue
        raw, is_opening = label[1]
        max_step = None if is_opening else _CHAPTER_MAX_STEP
        valid = [n for n in {_canonical_roman(raw), _canonical_roman(raw.replace("L", "I"))} if n
                 and (current is None or (current <= n and (max_step is None or n <= current + max_step)))]
        if valid:
            target = (current or 0) + 1
            n = min(valid, key=lambda v: (abs(v - target), v))
            resolved.append((off, ("chapter", n)))
            current = n
    return sorted(resolved, key=lambda x: x[0])


def _apply_section(parts: dict[str, Any], label) -> str:
    """Fold one section marker into the running state; return the section string."""
    if isinstance(label, tuple):
        kind, value = label
        if kind == "sthana_change":          # new sthana: chapter numbering restarts
            kind = "sthana"
            parts.pop("chapter", None)
        parts[kind] = value
        bits = [parts.get("sthana"), f"Chapter {parts['chapter']}" if parts.get("chapter") else None, parts.get("adhyaya")]
        return ", ".join(b for b in bits if b)
    return label


def header_at(context: dict[str, Any] | None, offset: int) -> str:
    """The "[Work] > [Section] > [Item]" header in effect at ``offset`` of a page."""
    if not context:
        return ""
    section, parts, item = context["section_in"], dict(context["parts_in"]), context["item_in"]
    for off, label in context["sections"]:
        if off > offset:
            break
        section = _apply_section(parts, label)
    for off, label in context["items"]:
        if off > offset:
            break
        item = label
    return " > ".join(p for p in (context["work"], section, item) if p)


def contextual_text(chunk: dict[str, Any]) -> str:
    """Text to embed / rerank: the context header (if any) on its own line, then the raw text."""
    text = chunk.get("text", "")
    header = (chunk.get("metadata") or {}).get("context_header")
    if settings.contextual_chunk_headers and header:
        return f"{header}\n{text}"
    return text
