# Eval Gold-Labeling Criteria (v2)

v2 (2026-10-29): adds the reviewer's Formulary rule for treatment/management
questions (§2) and the review-status provenance methods (§5).

How the gold labels in `eval_dataset.json` are assigned. Each item has two:
- `gold_works`: the **work-level** gold. A retrieved chunk counts as relevant
  when its work is one of these (`src/evaluation/retrieval_metrics.py`), so a
  label is a claim that this work answers the question.
- `gold_passages`: the **passage-level** gold, parent chunk ids the strict
  metric scores against (§2a). It is a subset of
  `provenance.supporting_chunk_ids`, the evidence behind the labels, but not
  always all of it.

## 1. The rule

A work is **gold** for a question if it **substantively answers** it. That means
it contains a passage that does at least one of the following for the question's
topic:

| Question type | Substantive means the work… |
|---|---|
| Drug properties (pharmacopoeia) | states the drug's own properties or actions (rasa, guṇa, vīrya, vipāka, karma, therapeutic action) |
| Formulation | gives the formulation's composition and/or its dose and indications |
| Clinical (disease) | defines, classifies, gives the etiology of, or gives treatment for the disease; for treatment/management questions, see the Formulary rule in §2 |
| Classical procedure / regimen | defines the procedure or regimen, gives its indications or method, or explains the asked-for rationale |

## 2. What does not count

- **Mentions are evidence, not the rule.** A work isn't gold because the term
  appears often in it.
- **Listing as an indication or ingredient.** An herb named in an ingredient
  list isn't gold for that herb's properties, and a disease named among a
  formulation's "therapeutic uses" isn't gold for a question about *classifying*
  or explaining the *cause* of that disease. The one exception follows.
- **Formulary rule (v2): for treatment/management questions, the Formulary IS
  gold** when it has formulation monographs indicated for that disease, i.e. a
  monograph whose "Important therapeutic uses" list names it. Prescribing an
  indicated formulation is treatment. Evidence is the whole monograph: every
  chunk from its parsed title to the next parsed title (`afi_monograph_spans`).
  The span is inclusive, so a citation the layout misplaced never splits a
  formulation from its uses list. It ends early only before a new group's
  introduction or the back matter. (Until 2026-10-29 evidence was only a chunk
  holding both the title and the uses list; changed at the reviewer's request.)
  This doesn't extend to classification or
  etiology-only questions, to the Pharmacopoeia's single-herb monographs, or past
  the scope rule in §3 (eval_024 names Sushruta, so it stays Sushruta-only).
  For these rows the supporting set lists **every** such monograph (a complete
  set, see `relabel_review.md`). That set is evidence for the work-level label.
  Only eval_017 also scores passages against it (§2a).
- **Group-level statements.** A property stated jointly for a group (for example
  "the following pot-herbs are heat-making in potency…") is **borderline**: it's
  recorded in the review notes but not made gold unless the question is about the
  group.
- **Index and contents pages.** A table of contents or index entry points to an
  answer but isn't one.
- **Retrieval output.** Labels must never be derived from what the system
  retrieves, or from eval results; that would make the eval measure itself.

## 2a. Passage-level gold (`gold_passages`)

By default a row's passage gold is its evidence, `provenance.supporting_chunk_ids`.
The exception, decided by the reviewer on 2026-10-30:

- **eval_018–023 and eval_025: Sushruta chapter passages only.** The Formulary
  stays in their `gold_works`, so any Formulary chunk still counts at the work
  level, but not at the passage level, for two reasons:
  - Formulations don't answer these questions. They ask for a line of
    treatment, an approach or a classification, and a monograph lists
    indications without describing any of that.
  - The complete monograph sets are too large to be a strict test. They cover
    8.6–21.0% of the Formulary's 903 pages with text (16.3–32.8% within ±1 page),
    or 10.1–28.3% of its 4,090 chunks (19.1–41.1% within ±1). For Jvara, a random
    Formulary chunk would count as a passage hit 41% of the time.
- **eval_017 keeps its Formulary set as passage gold:** it asks for formulations.
  The set is 51 parents: 4.2% of Formulary pages, 5.9% of its chunks.

## 3. Scope

- A question that names a work ("…in Sushruta") is gold only for that work, if it
  answers it.
- If no work substantively answers a question, the question is **flagged** for
  rewording or removal instead of being given a weak label. (eval_017 was flagged
  this way and reworded by the reviewer to "Which classical formulations are
  indicated for Amavata?")

## 4. Corpus caveats (as of 2026-10-29)

- **Charaka Samhita**: the English translation was OCR'd as Devanagari, so it
  can't be judged or matched by English queries. It's excluded from labeling and
  from the index (`settings.exclude_charaka`) until it's re-OCRed.
- **Ashtanga Hridaya**: only the English Vidyanath volume (Sūtrasthāna) is
  readable. The Srikantha Murthy vol 1 text layer is garbage and the commentaries
  are Devanagari-only; both are excluded from labeling and the index.
- **Ayurvedic Pharmacopoeia**: diacritics are stored in an old font encoding
  (`A¿vagandh¡` = Aśvagandhā); normalize them before searching for evidence.

## 5. Provenance

Every item carries a `provenance` object (see `eval_dataset.schema.json`):

| Field | Meaning |
|---|---|
| `method` | how the gold sources were assigned: `agent-proposed from corpus text, human-reviewed: pending` (current: proposed under these criteria and applied, awaiting row-by-row review); `agent-proposed from corpus text, human-reviewed` (only once the reviewer confirms); or `bm25-keyword-evidence` (legacy) |
| `criteria_version` | version of this document applied, or `null` for legacy labels |
| `labeled_on` | ISO date the labels were assigned |
| `source_commit` | commit holding the proposal the labels come from |
| `supporting_chunk_ids` | parent chunk ids that substantively answer the question: the evidence for `gold_works` (empty for legacy labels). `gold_passages` is the subset the passage metric uses |
| `reviewed_by` | who confirmed the labels; `null` while review is pending |

Proposals are written to `relabel_review.md` first. The reviewer (logn1602)
confirmed all 30 rows on 2026-10-29, eval_003 and eval_008 after a re-check.
Until confirmed, a row's provenance reads `…: pending` with `reviewed_by: null`
(enforced by `tests/test_eval_dataset.py`).
