"""
AyurKosha — Safety and Contraindication Layer
Ensures every answer includes relevant safety information.

Runs after generation + citation verification: scans the answer for herb
mentions (against data/synonyms/herb_synonyms.json), runs one targeted
semantic search per mentioned herb for contraindication passages, and
appends whatever safety-relevant sentences it finds. Also enforces the two
mandatory disclosures from the system prompt (src/generation/prompts.py):
a Rasa Shastra (mineral/metallic preparation) supervision warning, and the
practitioner-guidance closing line — appending either if the model omitted
it.

Fails safe: a failed lookup for one herb is logged and skipped; it never
blocks the rest of the answer.

Build this in: Phase 4, Step 7
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HERB_SYNONYMS_PATH = PROJECT_ROOT / "data" / "synonyms" / "herb_synonyms.json"

_VARIANT_KEYS = ("sanskrit", "latin", "hindi", "english", "ayurvedic", "modern")

_SAFETY_KEYWORDS = (
    "contraindicat", "caution", "avoid", "pregnan", "toxic",
    "interact", "overdose", "side effect",
)
_RASA_SHASTRA_KEYWORDS = ("rasa shastra", "bhasma", "parad", "mercury")

_RASA_SHASTRA_WARNING = (
    "Rasa Shastra (mineral/metallic) preparations mentioned above require "
    "expert preparation and supervision."
)
_PRACTITIONER_DISCLAIMER = (
    "This information is for educational and clinical reference purposes. "
    "Ayurvedic treatments should be administered under qualified "
    "practitioner (Vaidya) guidance."
)

_herb_names: list[str] | None = None


def _load_herb_names() -> list[str]:
    """Return all known herb name variants (all scripts), longest first.

    Longest-first ordering avoids a short synonym (e.g. "Harad") matching
    inside a longer unrelated word before a fuller variant gets a chance.
    """
    global _herb_names
    if _herb_names is not None:
        return _herb_names

    if not HERB_SYNONYMS_PATH.exists():
        logger.warning("Herb synonym file not found at %s; safety herb "
                       "detection disabled.", HERB_SYNONYMS_PATH)
        _herb_names = []
        return _herb_names

    try:
        with open(HERB_SYNONYMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read herb synonym file: %s", exc)
        _herb_names = []
        return _herb_names

    names: set[str] = set()
    for entry in data.values():
        if not isinstance(entry, dict):
            continue
        for key in _VARIANT_KEYS:
            for value in entry.get(key) or []:
                if isinstance(value, str) and value.strip():
                    names.add(value.strip())

    _herb_names = sorted(names, key=len, reverse=True)
    return _herb_names


def find_mentioned_herbs(answer: str) -> list[str]:
    """Return herb name variants that appear (case-insensitive) in `answer`."""
    lowered = answer.lower()
    return [name for name in _load_herb_names() if name.lower() in lowered]


def _relevant_sentences(text: str) -> list[str]:
    """Return sentences from `text` mentioning a safety keyword."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences
            if any(kw in s.lower() for kw in _SAFETY_KEYWORDS)]


def _contraindication_notes(herb: str) -> list[str]:
    """Run one targeted retrieval for `herb`'s contraindications, if any."""
    try:
        from src.retrieval.semantic import semantic_search

        results = semantic_search(f"{herb} contraindications safety precautions", top_n=3)
    except Exception as exc:  # noqa: BLE001 — never let a safety lookup break the answer
        logger.warning("Contraindication lookup failed for %s: %s", herb, exc)
        return []

    notes: list[str] = []
    for r in results:
        notes.extend(_relevant_sentences(r.get("text", "")))
        if notes:
            break  # top hit was enough; stop before spending more lookups
    return notes


def apply_safety_checks(answer: str, sources: list[dict[str, Any]]) -> str:
    """Append safety notes and mandatory disclosures to a generated answer.

    Args:
        answer: The (citation-verified) generated answer text.
        sources: The sources list used to generate the answer (from
            src/context/builder.py) — scanned alongside the answer for Rasa
            Shastra keywords.

    Returns:
        `answer` with a "Safety Notes" section appended when contraindication
        info was found, plus any missing mandatory disclosures.
    """
    herbs = find_mentioned_herbs(answer)
    safety_lines: list[str] = []
    for herb in herbs:
        notes = _contraindication_notes(herb)
        if notes:
            safety_lines.append(f"- {herb}: {' '.join(notes)}")

    combined_text = answer + " " + " ".join(s.get("document", "") for s in sources)
    if any(kw in combined_text.lower() for kw in _RASA_SHASTRA_KEYWORDS):
        safety_lines.append(f"- {_RASA_SHASTRA_WARNING}")

    result = answer
    if safety_lines:
        result += "\n\nSafety Notes:\n" + "\n".join(safety_lines)

    if _PRACTITIONER_DISCLAIMER not in result:
        result += f"\n\n{_PRACTITIONER_DISCLAIMER}"

    return result
