"""
AyurKosha — Ayurvedic Tokenizer
Custom BM25 tokenizer with Sanskrit/Devanagari support and synonym expansion.

This is one of the highest-impact components in the system: it is applied to
BOTH documents (at index time) and queries (at search time), so any expansion
or normalization it performs is symmetric across the corpus. The pipeline:

    1. Lowercase.
    2. Tokenize with a script-aware regex: Devanagari runs are kept whole,
       Latin/digit runs are separate tokens.
    3. Remove English stopwords.
    4. Synonym expansion: each Latin token is expanded to all known name
       variants from data/synonyms/ (via synonym_loader). Multi-word variants
       are split into their component word tokens so they match documents that
       tokenize the same phrase into words.
    5. Additive Porter stemming: English tokens are stemmed and the stem is
       ADDED alongside the surface form (not replaced). This lets
       "configuring" match "configuration" while keeping exact surface tokens
       available for precise matches. Devanagari tokens are never stemmed.
    6. De-duplicate while preserving first-seen order.

Stemming degrades gracefully: if NLTK is unavailable, surface tokens are still
produced and the stemming step is skipped.

Build this in: Phase 2 (one of the highest-impact components)
"""

from __future__ import annotations

import logging
import re

from src.ingestion.synonym_loader import get_synonyms

logger = logging.getLogger(__name__)

# Matches a run of Devanagari characters OR a run of Latin letters/digits.
# Everything else (punctuation, whitespace) is a delimiter.
_TOKEN_RE = re.compile(r"[ऀ-ॿ]+|[a-z0-9]+")

# Devanagari Unicode block, used to decide whether a token may be stemmed.
_DEVANAGARI_RE = re.compile(r"[ऀ-ॿ]")

STOPWORDS = {
    "the", "a", "an", "is", "are", "was", "were", "in", "on", "at",
    "to", "of", "for", "with", "by", "from", "and", "or", "but", "not",
    "this", "that", "these", "those", "it", "its",
    "as", "be", "been", "being", "has", "have", "had", "do", "does", "did",
    "which", "who", "whom", "what", "how", "when", "where", "why",
    "can", "could", "should", "would", "will", "shall", "may", "might",
}

# Domain acronyms that must NOT be expanded, stemmed, or otherwise altered.
# Notably "api" here means Ayurvedic Pharmacopoeia of India, not a programming
# interface — it is preserved as-is and never sent through synonym expansion.
DOMAIN_ACRONYMS = {"api", "afi", "gmp", "ayush", "ccras", "niimh", "fssai"}


def _get_stemmer():
    """Return a PorterStemmer instance, or None if NLTK is unavailable.

    PorterStemmer is a pure-algorithm stemmer and needs no downloaded corpora,
    so importing the class is sufficient. Cached on the function object.
    """
    if getattr(_get_stemmer, "_cached", "unset") != "unset":
        return _get_stemmer._cached
    try:
        from nltk.stem import PorterStemmer

        stemmer = PorterStemmer()
    except Exception as exc:  # ImportError or any NLTK init failure
        logger.warning(
            "NLTK PorterStemmer unavailable (%s); BM25 tokenizer will skip "
            "stemming. Install 'nltk' to enable stem-based matching.",
            exc,
        )
        stemmer = None
    _get_stemmer._cached = stemmer
    return stemmer


def _is_devanagari(token: str) -> bool:
    return bool(_DEVANAGARI_RE.search(token))


def _split_variant(variant: str) -> list[str]:
    """Lowercase a synonym variant and split it into word tokens.

    Uses the same token regex as the main tokenizer so that multi-word variants
    (e.g. "emblica officinalis") become the same tokens a document would
    produce for that phrase.
    """
    return _TOKEN_RE.findall(variant.lower())


def tokenize_ayurvedic(
    text: str,
    expand_synonyms: bool = True,
    stem: bool = True,
) -> list[str]:
    """Tokenize text for BM25 with Ayurvedic domain awareness.

    Handles Devanagari, synonym expansion, and additive Porter stemming.

    Args:
        text: Raw input text (query or document chunk).
        expand_synonyms: If True, expand recognized terms to all known name
            variants from the synonym dictionaries.
        stem: If True (and NLTK is available), add Porter stems of English
            tokens alongside their surface forms.

    Returns:
        List of tokens with duplicates removed, in first-seen order. Returns an
        empty list for empty/whitespace-only input.
    """
    if not text:
        return []

    text = text.lower()
    raw_tokens = _TOKEN_RE.findall(text)

    # Stage 1: surface tokens with stopwords removed.
    surface: list[str] = [t for t in raw_tokens if t not in STOPWORDS]

    # Stage 2: synonym expansion (Latin tokens only; Devanagari and protected
    # acronyms pass through unchanged).
    expanded: list[str] = []
    for token in surface:
        expanded.append(token)
        if not expand_synonyms:
            continue
        if _is_devanagari(token) or token in DOMAIN_ACRONYMS:
            continue
        for variant in get_synonyms(token):
            for word in _split_variant(variant):
                if word not in STOPWORDS:
                    expanded.append(word)

    # Stage 3: additive stemming of English tokens.
    stemmer = _get_stemmer() if stem else None
    if stemmer is not None:
        with_stems: list[str] = []
        for token in expanded:
            with_stems.append(token)
            if _is_devanagari(token) or token in DOMAIN_ACRONYMS:
                continue
            stemmed = stemmer.stem(token)
            if stemmed and stemmed != token:
                with_stems.append(stemmed)
        expanded = with_stems

    # Stage 4: de-duplicate, preserving first-seen order.
    seen: set[str] = set()
    result: list[str] = []
    for token in expanded:
        if token not in seen:
            seen.add(token)
            result.append(token)
    return result
