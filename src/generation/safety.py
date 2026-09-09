"""
AyurKosha — Safety and Contraindication Layer
Ensures every answer includes relevant safety information.

Runs after generation + citation verification. Two guarantees are always
enforced: the practitioner-guidance disclaimer, and a Rasa Shastra
(mineral/metallic preparation) supervision warning when such preparations are
mentioned. On top of that, it makes a best-effort attempt to surface
*herb-specific* contraindications from the corpus.

Precision matters here more than recall: a wall of loosely-related
"contraindication" text (procedure contraindications for vamana/vasti, OCR
noise, the same passage repeated per herb) is worse than nothing. So the
contraindication pass is deliberately conservative — it de-duplicates herbs to
one entry per plant, caps how many it looks up, and keeps a retrieved sentence
only when it carries a safety keyword *and* names the herb in question,
de-duplicating sentences globally. Herbs with no herb-specific hit contribute
no line at all; the mandatory disclaimers carry the baseline safety load.

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
    "interact", "overdose", "side effect", "adverse",
)
_RASA_SHASTRA_KEYWORDS = ("rasa shastra", "bhasma", "parad", "mercury")

# Minimum length for a herb-name variant to be used as a match trigger — short
# variants ("Bel", "Ela") produce too many false positives.
_MIN_VARIANT_LEN = 4
# Cap on herbs looked up per answer, and on note length, to keep the safety
# section tight and the Cohere cost bounded.
_MAX_HERBS_LOOKED_UP = 6
_MAX_NOTE_CHARS = 220

_RASA_SHASTRA_WARNING = (
    "Rasa Shastra (mineral/metallic) preparations mentioned above require "
    "expert preparation and supervision."
)
_PRACTITIONER_DISCLAIMER = (
    "This information is for educational and clinical reference purposes. "
    "Ayurvedic treatments should be administered under qualified "
    "practitioner (Vaidya) guidance."
)

# Cached herb entries: one per plant, with a display name + all name variants.
_herb_entries: list[dict[str, Any]] | None = None


def _load_herb_entries() -> list[dict[str, Any]]:
    """Return one entry per herb: {"display", "variants", "match_variants"}.

    ``variants`` is every name (lowercased) for sentence-level relevance;
    ``match_variants`` is the subset long enough (>= _MIN_VARIANT_LEN) to use as
    a whole-word trigger when scanning an answer. Grouping by plant here is what
    collapses the old "30 entries for ~6 herbs" explosion.
    """
    global _herb_entries
    if _herb_entries is not None:
        return _herb_entries

    if not HERB_SYNONYMS_PATH.exists():
        logger.warning("Herb synonym file not found at %s; safety herb "
                       "detection disabled.", HERB_SYNONYMS_PATH)
        _herb_entries = []
        return _herb_entries

    try:
        with open(HERB_SYNONYMS_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read herb synonym file: %s", exc)
        _herb_entries = []
        return _herb_entries

    entries: list[dict[str, Any]] = []
    for key, entry in data.items():
        if not isinstance(entry, dict):
            continue
        names: list[str] = []
        for vk in _VARIANT_KEYS:
            for value in entry.get(vk) or []:
                if isinstance(value, str) and value.strip():
                    names.append(value.strip())
        if not names:
            continue
        # Display name: prefer the first Sanskrit name, else the JSON key.
        sanskrit = entry.get("sanskrit") or []
        display = sanskrit[0] if sanskrit else key.replace("_", " ").title()
        variants = {n.lower() for n in names}
        match_variants = {v for v in variants if len(v) >= _MIN_VARIANT_LEN}
        entries.append({
            "display": display,
            "variants": frozenset(variants),
            "match_variants": frozenset(match_variants),
        })

    _herb_entries = entries
    return _herb_entries


def _word_present(needle: str, haystack_low: str) -> bool:
    """Whole-word, case-insensitive membership test."""
    return re.search(rf"\b{re.escape(needle)}\b", haystack_low) is not None


def mentioned_herb_entries(answer: str) -> list[dict[str, Any]]:
    """Herb entries (one per plant) whose name appears as a word in the answer."""
    low = answer.lower()
    return [e for e in _load_herb_entries()
            if any(_word_present(v, low) for v in e["match_variants"])]


def find_mentioned_herbs(answer: str) -> list[str]:
    """Display names of herbs mentioned in the answer (deduped, one per plant).

    Backwards-compatible thin wrapper over mentioned_herb_entries — returns the
    canonical display name for each detected plant.
    """
    return [e["display"] for e in mentioned_herb_entries(answer)]


def _relevant_sentences(text: str) -> list[str]:
    """Return sentences from `text` mentioning a safety keyword."""
    sentences = re.split(r"(?<=[.!?])\s+", text)
    return [s.strip() for s in sentences
            if any(kw in s.lower() for kw in _SAFETY_KEYWORDS)]


def _herb_contraindications(
    entry: dict[str, Any],
    seen: set[str],
) -> list[str]:
    """Best-effort herb-specific contraindication sentences for one herb.

    Keeps a sentence only when it carries a safety keyword AND names the herb
    (via one of its variants), so generic procedure-contraindication passages
    are filtered out. De-duplicates against `seen` (shared across herbs) so the
    same OCR passage isn't repeated, and truncates long OCR runs.
    """
    display = entry["display"]
    try:
        from src.retrieval.semantic import semantic_search

        results = semantic_search(f"{display} contraindications safety precautions", top_n=3)
    except Exception as exc:  # noqa: BLE001 — never let a safety lookup break the answer
        logger.warning("Contraindication lookup failed for %s: %s", display, exc)
        return []

    variants = entry["variants"]
    notes: list[str] = []
    for r in results:
        for sentence in _relevant_sentences(r.get("text", "")):
            low = sentence.lower()
            # Must actually name this herb — filters procedure/OCR noise.
            if not any(v in low for v in variants):
                continue
            norm = " ".join(low.split())
            if norm in seen:
                continue
            seen.add(norm)
            note = sentence if len(sentence) <= _MAX_NOTE_CHARS else sentence[:_MAX_NOTE_CHARS].rstrip() + "…"
            notes.append(note)
            break  # one solid sentence per herb is enough
        if notes:
            break
    return notes


def apply_safety_checks(answer: str, sources: list[dict[str, Any]]) -> str:
    """Append herb safety notes and mandatory disclosures to a generated answer.

    Args:
        answer: The (citation-verified) generated answer text.
        sources: The sources used to generate the answer (from
            src/context/builder.py) — scanned alongside the answer for Rasa
            Shastra keywords.

    Returns:
        `answer` with a "Safety Notes" section appended when herb-specific
        contraindications were found, plus any missing mandatory disclosures.
    """
    seen: set[str] = set()
    safety_lines: list[str] = []
    for entry in mentioned_herb_entries(answer)[:_MAX_HERBS_LOOKED_UP]:
        for note in _herb_contraindications(entry, seen):
            safety_lines.append(f"- {entry['display']}: {note}")

    combined_text = answer + " " + " ".join(s.get("document", "") for s in sources)
    if any(kw in combined_text.lower() for kw in _RASA_SHASTRA_KEYWORDS):
        safety_lines.append(f"- {_RASA_SHASTRA_WARNING}")

    result = answer
    if safety_lines:
        result += "\n\nSafety Notes:\n" + "\n".join(safety_lines)

    if _PRACTITIONER_DISCLAIMER not in result:
        result += f"\n\n{_PRACTITIONER_DISCLAIMER}"

    return result
