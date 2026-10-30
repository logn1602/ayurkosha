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
import re
import logging
from pathlib import Path

from config.settings import settings

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
# Same index keyed by folded romanization key (see _variant_key).
_synonym_key_index: dict[str, frozenset[str]] = {}
# Folded single words from the Sanskrit-language fields: "known Sanskrit".
_sanskrit_terms: frozenset[str] = frozenset()
_SANSKRIT_FIELDS = ("sanskrit", "hindi", "ayurvedic")


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


def _fold_lower(word: str) -> str:
    from src.ingestion.text_cleanup import fold_diacritics

    return fold_diacritics(word).lower()


def _variant_key(word: str) -> str:
    """Folded, romanization-keyed lookup form ("Ashwagandha" / "Aśvagandhā" -> "asvagandha")."""
    from src.utils.transliterate import romanization_key

    return romanization_key(_fold_lower(word))


def _sanskrit_like(token: str, sanskrit: frozenset[str], diacritic_tokens=frozenset()) -> bool:
    from src.utils.transliterate import english_words

    return token in diacritic_tokens or token in sanskrit or token not in english_words()


def _collect_sanskrit_terms(*dictionaries: dict) -> frozenset[str]:
    terms: set[str] = set()
    for dictionary in dictionaries:
        for entry in dictionary.values():
            if not isinstance(entry, dict):
                continue
            for field in _SANSKRIT_FIELDS:
                for value in entry.get(field) or ():
                    if isinstance(value, str):
                        terms.update(re.findall(r"[a-z]+", _fold_lower(value)))
    return frozenset(terms)


def _build_key_index(index: dict[str, frozenset[str]], sanskrit: frozenset[str]) -> dict[str, frozenset[str]]:
    """Re-key the Sanskrit-like part of the variant index by ``_variant_key`` (merging on collision)."""
    keyed: dict[str, set[str]] = {}
    for word, variants in index.items():
        if _sanskrit_like(_fold_lower(word), sanskrit):
            keyed.setdefault(_variant_key(word), set()).update(variants)
    return {key: frozenset(values) for key, values in keyed.items()}


def sanskrit_terms() -> frozenset[str]:
    """Folded words from the dictionaries' Sanskrit/Hindi/Ayurvedic name fields."""
    load_synonym_index()
    return _sanskrit_terms


def wants_romanization_key(token: str, diacritic_tokens=frozenset()) -> bool:
    """True for Sanskrit-like tokens, the only ones that get romanization keys.

    A (folded, lowercase) token qualifies if it came from a word written with
    IAST diacritics (``diacritic_tokens``), is a Sanskrit term from the synonym
    dictionaries, or is not a common English word. Plain English is excluded,
    so "ship" never becomes "sip".
    """
    load_synonym_index()
    return _sanskrit_like(token, _sanskrit_terms, diacritic_tokens)


def load_synonym_index(force_reload: bool = False) -> dict[str, frozenset[str]]:
    """Load (and cache) the synonym lookup index.

    Args:
        force_reload: Rebuild the index from disk even if already cached.

    Returns:
        Mapping of lowercased single-word variant -> frozenset of all variant
        strings for that entry. Empty if no synonym files are present.
    """
    global _synonym_index, _synonym_key_index, _sanskrit_terms
    if _synonym_index is not None and not force_reload:
        return _synonym_index

    herbs = _load_json(SYNONYMS_DIR / HERB_FILE)
    diseases = _load_json(SYNONYMS_DIR / DISEASE_FILE)
    index = _build_index(herbs, diseases)
    _sanskrit_terms = _collect_sanskrit_terms(herbs, diseases)
    _synonym_key_index = _build_key_index(index, _sanskrit_terms)
    _synonym_index = index
    logger.info("Loaded synonym index with %d variant keys.", len(_synonym_index))
    return _synonym_index


def get_synonyms(term: str) -> set[str]:
    """Return all known synonyms for a term, including the term itself.

    Lookup is case-insensitive. With ``settings.bm25_fold_diacritics`` on, it
    is also diacritic- and romanization-insensitive: "asvagandha" (folded
    IAST) finds the "Ashwagandha" entry. If the term is unknown, a
    single-element set containing the original term is returned (never raises).

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
    matches = set(index.get(term.lower(), ()))
    if settings.bm25_fold_diacritics and wants_romanization_key(_fold_lower(term)):
        matches |= _synonym_key_index.get(_variant_key(term), frozenset())
    if not matches:
        return {term}
    return matches | {term}
