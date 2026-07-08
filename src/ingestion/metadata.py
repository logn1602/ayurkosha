"""
AyurKosha — Metadata Extraction
Enriches loader records with structural metadata used for citations,
filtering, and chunk routing.

What it extracts (all heuristic, calibrated on the real corpus):

- text_name  : canonical work title inferred from the file name
               (e.g. "Charaka Samhita", "Ayurvedic Pharmacopoeia of India").
- Classical texts: `sthana` (Sutrasthana, Chikitsasthana, ...) and `chapter`
               from running headers / headings, plus a human `citation`.
- Pharmacopoeia / formulations: `is_monograph`, `monograph_sections`, and the
               Ayurvedic drug properties `rasa`, `guna`, `virya`, `vipaka`,
               `karma` when present as labelled fields.
- heading_path: ALL-CAPS heading candidates on the page.

All values are stored FLAT (str / list[str] / bool) because Pinecone metadata
does not allow nested objects.

NOTE on quality: property *values* extracted from the API PDF contain IAST
diacritic mojibake (a source font-encoding artifact); labels and structure are
reliable. Devanagari on some scans is garbled — see loaders.py notes.

Build this in: Phase 2, Step 2
"""

from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# ── Canonical work titles by file-name keyword ────────────────────────
# First matching keyword (checked in order) wins.
TEXT_NAME_BY_KEYWORD: list[tuple[str, str]] = [
    ("charaka", "Charaka Samhita"),
    ("caraka", "Charaka Samhita"),
    ("sushruta", "Sushruta Samhita"),
    ("susruta", "Sushruta Samhita"),
    ("ashtanga_hridaya", "Ashtanga Hridaya"),
    ("ashtanga_sangraha", "Ashtanga Sangraha"),
    ("madhava", "Madhava Nidana"),
    ("bhavaprakasha", "Bhavaprakasha"),
    ("api", "Ayurvedic Pharmacopoeia of India"),
    ("afi", "Ayurvedic Formulary of India"),
]

# ── Classical-text divisions (sthanas) across Brihattrayi ─────────────
# Stored lowercased, without a trailing "m" (Sutrasthana vs Sutrasthanam).
_STHANA_CANONICAL = {
    "sutrasthana": "Sutrasthana",
    "nidanasthana": "Nidanasthana",
    "vimanasthana": "Vimanasthana",
    "sharirasthana": "Sharirasthana",
    "sarirasthana": "Sharirasthana",
    "indriyasthana": "Indriyasthana",
    "chikitsasthana": "Chikitsasthana",
    "chikitsitasthana": "Chikitsasthana",
    "kalpasthana": "Kalpasthana",
    "siddhisthana": "Siddhisthana",
    "uttaratantra": "Uttaratantra",
    "uttarasthana": "Uttarasthana",
}

# "Chap. XXV", "Chapter 25", "Adhyaya 3" -> capture the numeral.
_CHAPTER_RE = re.compile(
    r"\b(?:chap(?:ter)?|adhyaya)\b\.?\s*([IVXLCDM]{1,7}|\d{1,3})\b",
    re.IGNORECASE,
)
# Matches a sthana token, tolerating a trailing "m".
_STHANA_RE = re.compile(
    r"\b([a-z]*sthana|uttaratantra|uttarasthana)m?\b",
    re.IGNORECASE,
)

# ── Pharmacopoeia / formulation monograph structure ───────────────────
MONOGRAPH_SECTION_HEADERS = {
    "SYNONYMS",
    "DESCRIPTION",
    "IDENTITY, PURITY AND STRENGTH",
    "CONSTITUENTS",
    "PROPERTIES AND ACTION",
    "THERAPEUTIC USES",
    "FORMULATIONS",
    "IMPORTANT FORMULATIONS",
    "DOSE",
    "MICROSCOPIC",
    "MACROSCOPIC",
}

# Ayurvedic drug-property fields, e.g. "Rasa : Katu, Tikta".
_PROPERTY_KEYS = {
    "rasa": "rasa",
    "guna": "guna",
    "guṇa": "guna",
    "virya": "virya",
    "vīrya": "virya",
    "vipaka": "vipaka",
    "vipāka": "vipaka",
    "karma": "karma",
}
_PROPERTY_RE = re.compile(
    r"^\s*(Rasa|Gu[nṇ]a|V[iī]rya|Vip[aā]ka|Karma)\s*[:：]\s*(.+?)\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Heading candidate: a short-ish ALL-CAPS line (letters/space/punct).
_HEADING_RE = re.compile(r"^[A-Z][A-Z0-9 ,.&()/'-]{2,48}$")

_ROMAN_MAP = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def infer_text_name(source: str) -> str | None:
    """Infer the canonical work title from a file name; None if unknown."""
    key = source.lower()
    for keyword, name in TEXT_NAME_BY_KEYWORD:
        if keyword in key:
            return name
    return None


def _roman_to_int(s: str) -> int | None:
    s = s.upper()
    if not all(ch in _ROMAN_MAP for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        val = _ROMAN_MAP[ch]
        total += -val if val < prev else val
        prev = max(prev, val)
    return total or None


def extract_chapter(text: str) -> str | None:
    """Return the first chapter/adhyaya numeral found (Arabic or Roman), as str."""
    m = _CHAPTER_RE.search(text)
    if not m:
        return None
    token = m.group(1)
    if token.isdigit():
        return token
    n = _roman_to_int(token)
    return str(n) if n else token


def extract_sthana(text: str) -> str | None:
    """Return the first recognized sthana (canonicalized), else None."""
    for m in _STHANA_RE.finditer(text):
        token = m.group(1).lower()
        if token in _STHANA_CANONICAL:
            return _STHANA_CANONICAL[token]
    return None


def extract_headings(text: str, limit: int = 5) -> list[str]:
    """Return up to `limit` ALL-CAPS heading candidates from the text."""
    headings: list[str] = []
    for line in text.split("\n"):
        line = line.strip()
        if _HEADING_RE.match(line) and not line.isdigit():
            headings.append(line)
            if len(headings) >= limit:
                break
    return headings


def extract_properties(text: str) -> dict[str, str]:
    """Extract Ayurvedic drug-property fields (rasa/guna/virya/vipaka/karma).

    Returns a mapping of canonical property key -> raw value string. Values may
    contain diacritic artifacts from the source PDF and are stored verbatim.
    """
    props: dict[str, str] = {}
    for m in _PROPERTY_RE.finditer(text):
        label = m.group(1).lower()
        key = _PROPERTY_KEYS.get(label)
        if key and key not in props:  # keep first occurrence
            props[key] = m.group(2).strip()
    return props


def detect_monograph_sections(text: str) -> list[str]:
    """Return the known monograph section headers present on the page."""
    found: list[str] = []
    for line in text.split("\n"):
        s = line.strip().upper()
        if s in MONOGRAPH_SECTION_HEADERS and s not in found:
            found.append(s)
    return found


def build_citation(meta: dict[str, Any]) -> str | None:
    """Build a human-readable citation string from enriched metadata."""
    name = meta.get("text_name")
    if not name:
        return None
    parts = [name]
    if meta.get("sthana"):
        parts.append(meta["sthana"])
    if meta.get("chapter"):
        parts.append(f"Chapter {meta['chapter']}")
    if meta.get("page") is not None:
        parts.append(f"p. {meta['page']}")
    return ", ".join(parts)


def enrich_record(record: dict[str, Any]) -> dict[str, Any]:
    """Enrich a single loader record in place with structural metadata.

    Dispatches on ``metadata['doc_type']``: classical texts get sthana/chapter/
    citation; pharmacopoeia and formulations get monograph flags + properties.

    Returns the same record (mutated) for convenience.
    """
    meta = record["metadata"]
    text = record.get("text", "")

    name = infer_text_name(meta.get("source", ""))
    if name:
        meta["text_name"] = name

    headings = extract_headings(text)
    if headings:
        meta["heading_path"] = headings

    doc_type = meta.get("doc_type")

    if doc_type == "classical_text":
        sthana = extract_sthana(text)
        chapter = extract_chapter(text)
        if sthana:
            meta["sthana"] = sthana
        if chapter:
            meta["chapter"] = chapter

    elif doc_type in ("pharmacopoeia", "formulation"):
        sections = detect_monograph_sections(text)
        props = extract_properties(text)
        meta["is_monograph"] = bool(sections or props)
        if sections:
            meta["monograph_sections"] = sections
        meta.update(props)  # flat rasa/guna/virya/vipaka/karma

    citation = build_citation(meta)
    if citation:
        meta["citation"] = citation

    return record


def enrich_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Enrich a list of loader records. Errors on one record are logged and skipped."""
    for record in records:
        try:
            enrich_record(record)
        except Exception as exc:  # never let one bad page abort enrichment
            logger.warning("Metadata enrichment failed for %s: %s",
                           record.get("metadata", {}).get("source"), exc)
    return records
