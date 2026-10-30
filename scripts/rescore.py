"""
AyurKosha — Rescore Saved Retrieval Runs
Recomputes Hit@k, Recall@k and MRR from saved retrieval traces (the JSONL each
eval run writes; see src/evaluation/traces.py) against any label file.

Zero API calls, and it needs neither the index nor the local stores the runs
used, so e.g. the "before" comparison can be rescored after labels change.

Run: python scripts/rescore.py data/eval/runs/before_20261101_100000
     python scripts/rescore.py run1.jsonl run2.jsonl --labels data/eval/eval_dataset.json --per-question
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, ValueError):  # pragma: no cover
    pass

from src.evaluation.run_eval import DEFAULT_DATASET
from src.evaluation.traces import labels_sha256, load_labels, per_question_table, read_trace, rescore


def trace_files(paths: list[str]) -> list[Path]:
    """Trace JSONL files named directly or found in the given directories (sorted)."""
    out: list[Path] = []
    for p in map(Path, paths):
        out.extend(sorted(p.glob("*.jsonl")) if p.is_dir() else [p])
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rescore saved retrieval traces (no API calls).")
    parser.add_argument("paths", nargs="+", help="Trace .jsonl files or directories holding them.")
    parser.add_argument("--labels", default=str(DEFAULT_DATASET), help="Eval dataset to score against.")
    parser.add_argument("--k", type=int, default=None, help="Cutoff (default: each run's own k).")
    parser.add_argument("--per-question", action="store_true", help="Also print first-gold ranks per question.")
    args = parser.parse_args(argv)

    labels = load_labels(args.labels)
    sha = labels_sha256(args.labels)
    files = trace_files(args.paths)
    if not files:
        print("No trace files found.", file=sys.stderr)
        return 1

    columns = []
    print(f"Labels: {args.labels} (sha256 {sha[:12]})\n")
    for path in files:
        meta, traces = read_trace(path)
        result = rescore(meta, traces, labels, args.k)
        k = args.k or meta["config"]["k"]
        r = result["summary"].get("retrieval", {})
        same = "same labels" if meta["labels_sha256"] == sha else "DIFFERENT labels from the run"
        print(f"{path.name}  [{meta['config']['name']}, index {meta['index']}, {meta['timestamp']}, {same}]")
        print(f"  Hit@{k} {r.get('hit_rate')}  Recall@{k} {r.get('recall_at_k')}  MRR {r.get('mrr')}"
              f"  (as run: {meta['summary'].get('retrieval')})")
        if result["missing"]:
            print(f"  skipped {len(result['missing'])} question(s) not in the label file: {result['missing']}")
        columns.append((f"{meta['config']['name']}@{meta['timestamp'][5:16]}", [traces]))
    if args.per_question:
        print()
        print("\n".join(per_question_table(columns, labels)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
