"""
AyurKosha — Synonym Dictionary Loader
Loads herb and disease synonym dictionaries and exposes fast synonym lookup
for BM25 query/document expansion (used by src/retrieval/tokenizer.py).

Design
------
The JSON files produced by scripts/build_synonyms.py group name variants by
language/script. This module flattens them into a single lookup:

    single-word variant (lowercased)  ->  set of ALL variant strings for that entry

Only *single-word* variants become lookup keys. Multi-word variants (e.g.
"Emblica officinalis", "Indian Gooseberry") still appear in the value set — so
expanding "amla" yields them — but they are not themselves keys, because their
individual words ("indian", "officinalis") are shared across many plants and
would introduce noise. The BM25 tokenizer splits multi-word variants into their
component word tokens on both the query and document side, so exact phrase keys
are unnecessary for matching.

The lookup is loaded once and cached at module level.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Project root: src/ingestion/synonym_loader.py -> parents[2] == project root.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
SYNONYMS_DIR = PROJECT_ROOT / "data" / "synonyms"

HERB_FILE = "herb_synonyms.json"
DISEASE_FILE = "disease_synonyms.json"

# Keys within each entry that hold lists of name variants. "family" and any
# future property fields (rasa/guna/virya) are intentionally excluded.
_VARIANT_KEYS = ("sanskrit", "latin", "hindi", "english", "ayurvedic", "modern")

# Module-level cache: variant token -> frozenset of all synonym strings.
_synonym_index: dict[str, frozenset[str]] | None = None


def _load_json(path: Path) -> dict:
    """Load a synonym JSON file, returning {} if it is missing."""
    if not path.exists():
        logger.warning(
            "Synonym file not found: %s. Run scripts/build_synonyms.py to "
            "generate it. Synonym expansion will be disabled for this file.",
            path,
        )
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("Failed to read synonym file %s: %s", path, exc)
        return {}


def _collect_variants(entry: dict) -> set[str]:
    """Collect all name-variant strings from a single dictionary entry."""
    variants: set[str] = set()
    for key in _VARIANT_KEYS:
        values = entry.get(key)
        if not values:
            continue
        for value in values:
            if isinstance(value, str) and value.strip():
                variants.add(value.strip())
    return variants


def _build_index(*dictionaries: dict) -> dict[str, frozenset[str]]:
    """Build the flat single-word-variant -> all-variants lookup.

    When the same key appears in more than one entry (e.g. "krishna" is a
    Sanskrit synonym for both Maricha and Pippali), the variant sets are merged
    so the expansion is a superset rather than being silently overwritten.
    """
    index: dict[str, set[str]] = {}
    for dictionary in dictionaries:
        for entry in dictionary.values():
            if not isinstance(entry, dict):
                continue
            variants = _collect_variants(entry)
            for variant in variants:
                # Only single-word variants become lookup keys (see module docstring).
                if " " in variant:
                    continue
                index.setdefault(variant.lower(), set()).update(variants)
    return {key: frozenset(values) for key, values in index.items()}


def load_synonym_index(force_reload: bool = False) -> dict[str, frozenset[str]]:
    """Load (and cache) the synonym lookup index.

    Args:
        force_reload: Rebuild the index from disk even if already cached.

    Returns:
        Mapping of lowercased single-word variant -> frozenset of all variant
        strings for that entry. Empty if no synonym files are present.
    """
    global _synonym_index
    if _synonym_index is not None and not force_reload:
        return _synonym_index

    herbs = _load_json(SYNONYMS_DIR / HERB_FILE)
    diseases = _load_json(SYNONYMS_DIR / DISEASE_FILE)
    _synonym_index = _build_index(herbs, diseases)
    logger.info("Loaded synonym index with %d variant keys.", len(_synonym_index))
    return _synonym_index


def get_synonyms(term: str) -> set[str]:
    """Return all known synonyms for a term, including the term itself.

    Lookup is case-insensitive. If the term is unknown, a single-element set
    containing the original term is returned (never raises).

    Args:
        term: A single word (already tokenized). Multi-word input is not
            expected here; pass individual tokens.

    Returns:
        Set of synonym strings (original casing preserved from the dictionary),
        always including ``term`` itself.
    """
    if not term:
        return set()
    index = load_synonym_index()
    matches = index.get(term.lower())
    if matches is None:
        return {term}
    return set(matches) | {term}
