# Saved comparison runs

One folder per comparison phase, written by `scripts/run_comparison.py --phase <before|after> --run`:

| File | What it holds |
|---|---|
| `eval_<ts>_<config>.json` | the run's per-question metrics and summary |
| `eval_<ts>_<config>.jsonl` | the **retrieval trace**: a run header (config, index, text flags, retrieval params, labels file + sha256, timestamp, summary), then one line per question with the ranked candidates at each stage (`fused`, `rerank`, `mmr`): chunk id, work, source, page, stage score |
| `per_question.md` | summary table (Hit@6, Recall@6, **MRR@6** as the headline MRR, plus full-list MRR@15, n/a for rerank_mmr), then the rank of the first gold hit per question and config, with `+`/`-`/`=` where rerank helps or hurts |
| `comparison.json` | the phase's summaries (rescored against the labels at run time) |

Commit each folder. The traces make a run independent of the index and stores it ran
on: `scripts/rescore.py` recomputes Hit@6, Recall@6, MRR@6 and MRR@15 against any label file
with zero API calls.

```bash
python scripts/rescore.py data/eval/runs/before_<ts> --per-question
python scripts/rescore.py data/eval/runs/before_<ts> --labels path/to/other_labels.json
```
