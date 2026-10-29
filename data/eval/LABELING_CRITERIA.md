# Eval Gold-Labeling Criteria (v1)

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
| Clinical (disease) | defines, classifies, gives the etiology of, or gives treatment for the disease |
| Classical procedure / regimen | defines the procedure or regimen, gives its indications or method, or explains the asked-for rationale |

## 2. What does not count

- **Mentions are evidence, not the rule.** A work isn't gold because the term
  appears often in it.
- **Listing as an indication or ingredient.** For example, the Formulary listing
  Jvara among a formulation's "therapeutic uses" doesn't make it gold for a
  question about classifying or treating Jvara. An herb named in an ingredient
  list isn't gold for that herb's properties.
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
  rewording or removal instead of being given a weak label.

## 4. Corpus caveats (as of 2026-10-29)

- **Charaka Samhita**: the indexed text is garbled Devanagari OCR, so it can't be
  judged or matched by English queries. It's excluded from labeling until it's
  re-OCRed (and excluded from the index behind `settings.exclude_charaka`).
- **Ashtanga Hridaya**: only the English Sūtrasthāna volumes are readable. The
  Devanagari commentary volume can't be judged.
- **Ayurvedic Pharmacopoeia**: diacritics are stored in an old font encoding
  (`A¿vagandh¡` = Aśvagandhā); normalize them before searching for evidence.

## 5. Provenance

Every item carries a `provenance` object (see `eval_dataset.schema.json`):

| Field | Meaning |
|---|---|
| `method` | how the gold sources were assigned, e.g. `bm25-keyword-evidence` (legacy) or `corpus-evidence-v1` (these criteria) |
| `criteria_version` | version of this document applied, or `null` for legacy labels |
| `labeled_on` | ISO date the labels were assigned |
| `source_commit` | commit that introduced the labels |
| `supporting_chunk_ids` | parent chunk ids that substantively answer the question (empty for legacy labels) |
| `reviewed_by` | who approved the labels, or `null` if unreviewed |

Proposals are written to `relabel_review.md` first. Labels are changed in the
dataset only after human approval.
