"""
AyurKosha — Corpus Character Inventory
Lists every non-ASCII, non-Devanagari character in the indexed corpus
(data/cache/parent_store.json) by frequency, with per-work counts and sample
words. With --after-map, re-runs the inventory on text passed through the
proposed legacy-font map (src/ingestion/text_cleanup.py) to show what is left.

No API calls.

Run: python scripts/char_inventory.py [--work API] [--after-map] [--top 60]
"""

import argparse
import collections
import json
import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from src.ingestion.metadata import infer_text_name
from src.ingestion.parent_store import DEFAULT_STORE_PATH
from src.ingestion.text_cleanup import fix_font_artifacts

SHORT = {"Ayurvedic Pharmacopoeia of India": "API", "Ayurvedic Formulary of India": "AFI",
         "Sushruta Samhita": "SS", "Ashtanga Hridaya": "AH", "Charaka Samhita": "CS"}
_ODD = re.compile(r"[^\x00-\x7Fऀ-ॿ]")
# IAST letters a correct decode should produce — not counted as residue.
_IAST = set("āīūṛṝḷṅñṭḍṇśṣṃḥĀĪŪṚṜḶṄÑṬḌṆŚṢṂḤ")


def main():
    parser = argparse.ArgumentParser(description="Inventory odd characters in the corpus.")
    parser.add_argument("--work", choices=sorted(SHORT.values()), help="Restrict to one work.")
    parser.add_argument("--after-map", action="store_true", help="Apply the proposed char map first.")
    parser.add_argument("--top", type=int, default=60)
    args = parser.parse_args()

    store = json.loads(Path(DEFAULT_STORE_PATH).read_text(encoding="utf-8"))
    counts = collections.Counter()
    by_work = collections.defaultdict(collections.Counter)
    words = collections.defaultdict(collections.Counter)
    for parent in store.values():
        name = infer_text_name(parent["metadata"]["source"])
        work = SHORT.get(name, "?")
        if args.work and work != args.work:
            continue
        text = fix_font_artifacts(parent["text"], name) if args.after_map else parent["text"]
        for m in _ODD.finditer(text):
            ch = m.group()
            if args.after_map and ch in _IAST:
                continue
            counts[ch] += 1
            by_work[ch][work] += 1
            start, end = m.start(), m.end()
            while start > 0 and not text[start - 1].isspace():
                start -= 1
            while end < len(text) and not text[end].isspace():
                end += 1
            words[ch][text[start:end][:30]] += 1

    print(f"{len(counts)} distinct characters, {sum(counts.values())} occurrences"
          + (" (after proposed map, IAST excluded)" if args.after_map else ""))
    for ch, n in counts.most_common(args.top):
        name = unicodedata.name(ch, "?")[:26]
        works = ", ".join(f"{w} {c}" for w, c in by_work[ch].most_common(3))
        samples = " | ".join(w for w, _ in words[ch].most_common(4))
        print(f"U+{ord(ch):04X} {ch!r:6} {name:26} {n:6}  [{works}]  {samples}")


if __name__ == "__main__":
    main()
