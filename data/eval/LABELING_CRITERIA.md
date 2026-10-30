# Eval Gold-Labeling Criteria (v2)

v2 (2026-10-29): adds the reviewer's Formulary rule for treatment/management
questions (§2) and the review-status provenance methods (§5).

How `gold_sources` in `eval_dataset.json` are assigned. Retrieval metrics are
scored at the **work level** (`src/evaluation/retrieval_metrics.py`): a retrieved
chunk counts as relevant when its work is one of the question's gold works. So a
gold label is a claim that this work answers the question.

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
  set, see `relabel_review.md`), so the passage-level metric can credit any
  indicated formulation.
- **Group-level statements.** A property stated jointly for a group (for example
  "the following pot-herbs are heat-making in potency…") is **borderline**: it's
  recorded in the review notes but not made gold unless the question is about the
  group.
- **Index and contents pages.** A table of contents or index entry points to an
  answer but isn't one.
- **Retrieval output.** Labels must never be derived from what the system
  retrieves, or from eval results; that would make the eval measure itself.

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
| `supporting_chunk_ids` | parent chunk ids that substantively answer the question (empty for legacy labels) |
| `reviewed_by` | who confirmed the labels; `null` while review is pending |

Proposals are written to `relabel_review.md` first. The reviewer (logn1602)
confirmed all 30 rows on 2026-10-29, eval_003 and eval_008 after a re-check.
Until confirmed, a row's provenance reads `…: pending` with `reviewed_by: null`
(enforced by `tests/test_eval_dataset.py`).
