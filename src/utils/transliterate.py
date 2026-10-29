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
