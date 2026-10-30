"""
AyurKosha — chapter-level passage gold for the Sushruta disease rows (offline, no API calls)

For eval_018–025, a cited Sushruta page stands for its whole chapter: the
row's ``gold_passages`` become every parent chunk of the chapter each cited
page belongs to. Chapters are read from the context headers (the same code
that heads the chunks), so gold and headers agree: a parent is in the chapter
when one of its chunks is headed with it.

A chapter longer than MAX_CHAPTER_PAGES keeps page-level gold, as a guard
against mixed-topic chapters (Sutrasthana 46 runs ~100 pages), unless it is a
listed single-topic chapter. Herb/property rows and AH/API passages are not
touched.

Usage:
    python scripts/build_chapter_passages.py            # report only
    python scripts/build_chapter_passages.py --write    # also update data/eval/eval_dataset.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from src.evaluation.retrieval_metrics import parse_support_id  # noqa: E402
from src.ingestion.chunkers import (CHILD_CHUNK_SIZE, CHILD_OVERLAP, PARENT_CHUNK_SIZE, PARENT_OVERLAP,  # noqa: E402
                                    _WordLocator, split_text)
from src.ingestion.context_headers import annotate_context, header_at  # noqa: E402

SS = "Sushruta Samhita"
STORE = Path("data/cache/parent_store.json")
DATASET = Path("data/eval/eval_dataset.json")
ROWS = ("eval_018", "eval_019", "eval_020", "eval_021", "eval_022", "eval_023", "eval_024", "eval_025")
MAX_CHAPTER_PAGES = 25
SINGLE_TOPIC = {("sushruta_samhita_vol_3.pdf", "Uttaratantra, Chapter 39")}     # Jvara: one disease throughout
_PART_RE = re.compile(r"_P(\d+)$")


def chunk_chapters(store: dict) -> tuple[dict, dict]:
    """({(source, page): Counter of chapters of its chunks}, {(source, chapter): {parent ids}})."""
    pages = defaultdict(list)
    for pid, parent in store.items():
        meta = parent["metadata"]
        if meta["source"].startswith("sushruta"):
            pages[(meta["source"], meta.get("page") or 0)].append((int(_PART_RE.search(pid).group(1)), pid, parent["text"]))
    records = [{"text": "\n".join(t for _, _, t in sorted(pages[k])), "metadata": {"source": k[0], "page": k[1],
                                                                                  "text_name": SS}} for k in sorted(pages)]
    annotate_context(records)
    by_page, by_chapter = defaultdict(Counter), defaultdict(set)
    for record in records:
        key = (record["metadata"]["source"], record["metadata"]["page"])
        ids = [pid for _, pid, _ in sorted(pages[key])]
        loc = _WordLocator(record["text"])
        for pi, ptext in enumerate(split_text(record["text"], PARENT_CHUNK_SIZE, PARENT_OVERLAP)):
            for ctext in split_text(ptext, CHILD_CHUNK_SIZE, CHILD_OVERLAP):
                chapter = header_at(record["context"], loc.midpoint(ctext)).removeprefix(f"{SS} > ")
                if ", Chapter " in chapter:
                    by_page[key][chapter] += 1
                    by_chapter[(key[0], chapter)].add(ids[min(pi, len(ids) - 1)])
    return by_page, by_chapter


def _page(pid: str) -> int:
    return parse_support_id(pid)[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--write", action="store_true", help="update the dataset's gold_passages and gold_chapters")
    args = parser.parse_args()

    by_page, by_chapter = chunk_chapters(json.loads(STORE.read_text(encoding="utf-8")))
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    rows = {x["id"]: x for x in data}
    for qid in ROWS:
        item = rows[qid]
        cited = [c for c in item["provenance"]["supporting_chunk_ids"] if c.startswith("sushruta")]
        chapters, notes = [], []
        for pid in cited:
            stem, page = parse_support_id(pid)
            source = stem[: -len("_pdf")] + ".pdf"
            counts = by_page[(source, page)]
            chapter = counts.most_common(1)[0][0]
            if len(counts) > 1:
                notes.append(f"p{page} holds {dict(counts)}; taken as {chapter}")
            if (source, chapter) not in chapters:
                chapters.append((source, chapter))
        spans, passages, page_level = [], [], False
        for source, chapter in chapters:
            ids = sorted(by_chapter[(source, chapter)], key=_page)
            first, last = _page(ids[0]), _page(ids[-1])
            inside = all(first <= parse_support_id(c)[1] <= last for c in cited
                         if parse_support_id(c)[0] == source[:-4] + "_pdf" and by_page[(source, parse_support_id(c)[1])]
                         .most_common(1)[0][0] == chapter)
            n_pages = last - first + 1
            too_long = n_pages > MAX_CHAPTER_PAGES and (source, chapter) not in SINGLE_TOPIC
            page_level |= too_long
            spans.append({"source": source, "chapter": chapter, "first_page": first, "last_page": last})
            passages += ids
            flag = " (over the cap: page-level gold)" if too_long else \
                " (over the cap, single-topic: chapter-level)" if n_pages > MAX_CHAPTER_PAGES else ""
            print(f"{qid} {source[:22]} {chapter:28} p{first}-{last}: {n_pages} pages, {len(ids)} parents; "
                  f"cited pages inside: {inside}{flag}")
        for note in notes:
            print(f"{qid}   note: {note}")
        if args.write and not page_level:
            item["gold_passages"] = [p for p in item["gold_passages"] if not p.startswith("sushruta")] + passages
            item["gold_chapters"] = spans
    if args.write:
        DATASET.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"wrote {DATASET}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
