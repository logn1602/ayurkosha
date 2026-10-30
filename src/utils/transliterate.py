"""
AyurKosha — Sanskrit Transliteration Utilities
Normalizes the many romanizations of the same Sanskrit word.

The corpus and its users spell Sanskrit three ways:
  - popular romanization (users, the synonym dictionaries, Sushruta's
    translator): "Ashwagandha", "Shatavari", "Guduchi", "Ghrita"
  - IAST (Pharmacopoeia): "Aśvagandhā", "Śatāvarī", "Guḍūcī", "Ghṛta",
    which diacritic folding turns into "asvagandha", "satavari", "guduci", "ghrta"
  - folded-IAST ASCII (Formulary): "asvagandha", "satavari", "guduci"

Folding diacritics (src/ingestion/text_cleanup.fold_diacritics) only bridges
IAST and folded IAST. ``romanization_key`` closes the remaining gap by
collapsing the popular-vs-IAST letter choices, so every spelling of a word
shares one key:

    ashwagandha / asvagandha / aśvagandhā    -> "asvagandha"
    shatavari   / satavari   / śatāvarī      -> "satavar"
    guduchi     / guduci     / guḍūcī        -> "guduci"
    krishna     / kṛṣṇa                      -> "krsna"

The key is a matching form, not a spelling to display. The BM25 tokenizer
adds it alongside the surface token, and the synonym index is also keyed by
it (see src/retrieval/tokenizer.py, src/ingestion/synonym_loader.py).

Keys are only given to Sanskrit-like tokens (synonym_loader.wants_romanization_key):
applied to plain English, the same rules merge unrelated words (ship/sip,
wine/vine, shore/sore, food/fud). ``english_words`` is the English side of
that test.

TODO (unchanged): Devanagari <-> IAST conversion (e.g. via
indic-transliteration) for Devanagari queries.

Build this in: Phase 2 (useful for tokenizer and metadata)
"""

from __future__ import annotations

# Applied in order to a lowercase, diacritic-folded ASCII token. Each maps a
# popular-romanization spelling onto what folded IAST writes for the same sound.
_RULES: tuple[tuple[str, str], ...] = (
    ("chh", "c"),   # popular chh = IAST ch (aspirated) -> both collapse to c
    ("ch", "c"),    # popular ch  = IAST c   (Guduchi / Guḍūcī)
    ("sh", "s"),    # popular sh  = IAST ś/ṣ (Shatavari / Śatāvarī, Gokshura / Gokṣura)
    ("w", "v"),     # popular w   = IAST v   (Ashwagandha / Aśvagandhā)
    ("aa", "a"),    # doubled vowels for long vowels (Peepli / Pīpli)
    ("ee", "i"),
    ("oo", "u"),
    ("ri", "r"),    # popular ri  = IAST ṛ   (Ghrita / Ghṛta, Krishna / Kṛṣṇa)
)
_MIN_LEN = 3
# Tokens among the most frequent English words never get a key. At 50k the
# list covers the common words the rules would merge (ship 1071, wine 2314,
# shore 3242) while holding almost no Sanskrit: only pandu/rasa/pitta, whose
# keys are themselves, and names like krishna, which the synonym dictionary
# flags as Sanskrit anyway.
ENGLISH_TOP_N = 50_000
_english_words: frozenset[str] | None = None


def english_words() -> frozenset[str]:
    """The ENGLISH_TOP_N most frequent English words (wordninja's frequency list)."""
    global _english_words
    if _english_words is None:
        import gzip
        import os

        import wordninja

        path = os.path.join(os.path.dirname(wordninja.__file__), "wordninja", "wordninja_words.txt.gz")
        with gzip.open(path) as f:
            _english_words = frozenset(f.read().decode().split()[:ENGLISH_TOP_N])
    return _english_words


def romanization_key(token: str) -> str:
    """Spelling-variant-insensitive key for one lowercase ASCII token.

    Tokens shorter than 3 letters, or containing anything but ASCII
    letters, are returned unchanged.
    """
    if len(token) < _MIN_LEN or not (token.isascii() and token.isalpha()):
        return token
    key = token
    for old, new in _RULES:
        key = key.replace(old, new)
    return key
