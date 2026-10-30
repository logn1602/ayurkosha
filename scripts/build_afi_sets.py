"""
AyurKosha — rebuild the Formulary supporting sets (offline, no API calls)

For the treatment questions, the Formulary part of a question's supporting set
is every chunk of every monograph whose therapeutic-uses list names the
disease. Monographs are ``afi_monograph_spans``: inclusive, so a formulation
ends only at the next parsed title (or at a group introduction / the back
matter, both after its uses list). They are read from the current parent
store, so the ids are its parent ids.

Reported per question: set size now vs before, the monographs, uses lists that
name the disease but sit outside every span (lost: no title to attach them to),
and selected spans holding more than one uses list (a title inside was not
parsed, so the span also covers an untitled formulation).

Usage:
    python scripts/build_afi_sets.py            # report only
    python scripts/build_afi_sets.py --write    # also update data/eval/eval_dataset.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.ingestion.context_headers import afi_monograph_spans, afi_uses_lists  # noqa: E402
from src.ingestion.text_cleanup import fix_font_artifacts, fold_diacritics  # noqa: E402

AFI = "Ayurvedic Formulary of India"
STORE = Path("data/cache/parent_store.json")
DATASET = Path("data/eval/eval_dataset.json")
DISEASES = {
    "eval_017": ("Amavata", r"\ba+mavata"),
    "eval_018": ("Jvara", r"j[vw]ara"),
    "eval_019": ("Prameha", r"prameha|madhumeha|\bmeha\b"),
    "eval_020": ("Grahani", r"grahani"),
    "eval_021": ("Atisara", r"atisara"),
    "eval_022": ("Pandu", r"\bpandu"),
    "eval_023": ("Kasa", r"\bkasa\b|\bkasaroga"),
    "eval_025": ("Kustha", r"kus(h)?tha"),
}
_PART_RE = re.compile(r"_P(\d+)$")


def page_records(store: dict) -> tuple[list[dict], dict]:
    """Formulary page records rebuilt from the parent store, and each page's parent offsets."""
    parents = defaultdict(list)
    for pid, parent in store.items():
        meta = parent["metadata"]
        if meta.get("text_name") == AFI or meta["source"].startswith("afi"):
            parents[(meta["source"], meta.get("page") or 0)].append(
                (int(_PART_RE.search(pid).group(1)), pid, fix_font_artifacts(parent["text"], AFI)))
    records, offsets = [], {}
    for key in sorted(parents):
        text, spans = "", []
        for _, pid, part in sorted(parents[key]):
            text += " " if text else ""
            spans.append((pid, len(text), len(text) + len(part)))
            text += part
        records.append({"text": text, "metadata": {"source": key[0], "page": key[1], "text_name": AFI}})
        offsets[key] = spans
    return records, offsets


def _key(pos):
    return (pos[0], float("inf") if pos[1] is None else pos[1])


def _inside(span: dict, page: int, offset: float) -> bool:
    return _key(span["start"]) <= (page, offset) and (span["end"] is None or (page, offset) < _key(span["end"]))


def monographs(records: list[dict], offsets: dict) -> tuple[list[dict], list[dict]]:
    """(spans with their parent ids and uses lists, uses lists outside every span)."""
    spans = afi_monograph_spans(records)
    by_source = defaultdict(list)
    for span in spans:
        span.update(parents=[], uses=[])
        by_source[span["source"]].append(span)
    stray = []
    for record in records:
        src, page = record["metadata"]["source"], record["metadata"]["page"]
        for pid, a, b in offsets[(src, page)]:
            for span in by_source[src]:
                if _inside(span, page, a) or _inside(span, page, b - 1) or (
                        span["start"][0] == page and a <= span["start"][1] < b):
                    span["parents"].append(pid)
        for off, uses in afi_uses_lists(record["text"]):
            pid = next(p for p, a, b in offsets[(src, page)] if a <= off < b + 1)
            entry = {"source": src, "page": page, "parent": pid, "text": fold_diacritics(uses).lower()}
            owner = next((s for s in by_source[src] if _inside(s, page, off)), None)
            (owner["uses"] if owner else stray).append(entry)
    return spans, stray


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="update the dataset's Formulary supporting ids")
    args = parser.parse_args()

    store = json.loads(STORE.read_text(encoding="utf-8"))
    spans, stray = monographs(*page_records(store))
    multi = sum(1 for s in spans if len(s["uses"]) > 1)
    print(f"Formulary spans: {len(spans)}; with a uses list: {sum(1 for s in spans if s['uses'])}; "
          f"with 2+ (an untitled formulation inside): {multi}; uses lists outside every span: {len(stray)}\n")

    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rows = {x["id"]: x for x in data}
    results = {}
    for qid, (disease, pattern) in DISEASES.items():
        rx = re.compile(pattern)
        chosen = [s for s in spans if any(rx.search(u["text"]) for u in s["uses"])]
        ids = sorted({pid for s in chosen for pid in s["parents"]}, key=lambda p: (p.rsplit("_", 2)[0], *map(int, re.findall(r"\d+", p)[-2:])))
        before = [c for c in rows[qid]["provenance"]["supporting_chunk_ids"] if c.startswith("afi")]
        lost = [u for u in stray if rx.search(u["text"])]
        results[qid] = ids
        print(f"{qid} {disease}: AFI chunks {len(before)} -> {len(ids)} "
              f"(+{len(set(ids) - set(before))} / -{len(set(before) - set(ids))}); monographs {len(chosen)}")
        for s in chosen:
            pages = (s["end"][0] if s["end"] else s["start"][0]) - s["start"][0] + 1
            flags = [f"{len(s['uses'])} uses lists"] if len(s["uses"]) > 1 else []
            flags += [f"{pages} pages"] if pages >= 4 else []
            first_hit = next(i for i, u in enumerate(s["uses"]) if rx.search(u["text"]))
            flags += ["disease in a later list, not the first"] if first_hit else []
            print(f"    {s['number'] or '-':6} {s['title']:34} p{s['start'][0]}"
                  f"{'-' + str(s['end'][0]) if s['end'] and s['end'][0] != s['start'][0] else ''}"
                  f"  chunks {len(s['parents'])}{'  [' + '; '.join(flags) + ']' if flags else ''}")
        for u in lost:
            print(f"    LOST  {u['parent']}: {' '.join(u['text'].split())[:110]}")
        print()

    if args.write:
        for qid, ids in results.items():
            prov = rows[qid]["provenance"]
            prov["supporting_chunk_ids"] = [c for c in prov["supporting_chunk_ids"] if not c.startswith("afi")] + ids
            passages = rows[qid]["gold_passages"]
            if any(c.startswith("afi") for c in passages):      # eval_017: the AFI set is its passage gold
                rows[qid]["gold_passages"] = [c for c in passages if not c.startswith("afi")] + ids
        DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {DATASET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
