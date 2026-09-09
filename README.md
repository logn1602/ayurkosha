# AyurKosha

**The Ayurvedic Knowledge Treasury** — A hybrid search RAG system with verified citations over classical Ayurvedic texts, pharmacopoeia, research literature, and clinical guidelines.

## What It Does

Ask any Ayurvedic question → get a direct, cited answer traceable to the exact source text, chapter, and verse. Every claim is verified. Every formulation includes safety information.

## Architecture

```
Query → Expansion → Semantic + BM25 → RRF Fusion → Cohere Rerank → MMR → Context Assembly → Claude → Citation Verify → Answer
```

**8 RAG patterns:** Hybrid Search, RAG-Fusion, Reranking, Query Transformation, Parent-Child Retrieval, Self-Corrective, Graph (planned), Adaptive (planned).

## Evaluation & Results

AyurKosha ships with a **30-question evaluation harness** (`scripts/run_eval.py`) spanning pharmacopoeia, formulation, clinical, and classical categories, with gold sources grounded in the actual corpus. Retrieval metrics run fully offline (no LLM cost); an optional Claude LLM-judge scores answer quality.

**Retrieval quality** — does the correct source reach the model's context?

| Metric | Score |
|---|---|
| Hit rate (gold source in top-6) | **~0.90** |
| Recall@6 | **~0.73** |
| MRR | **~0.67** |

**Answer quality** — Claude LLM-as-judge, 0–10, across 30 questions:

| Metric | Score |
|---|---|
| Faithfulness | **7.6 / 10** |
| Relevance | **8.5 / 10** |
| Completeness | **7.5 / 10** |
| Citation accuracy | **100%** — 0 hallucinated citations |
| Safety disclaimer present | **100%** |

> *Retrieval figures are averaged over runs and vary by ±~0.05 due to reranker and vector-search nondeterminism. Gold sources are matched at the work level from keyword evidence; single-herb monograph retrieval (pharmacopoeia) is the current soft spot (MRR ≈ 0.5).*

```bash
make eval-retrieval                   # offline, no API cost
python scripts/run_eval.py --judge    # adds LLM-judge answer scores
```

## Grounding & Safety

Every factual claim is checked against the retrieved sources: **citations that don't map to a real source are stripped and reported**, and the system **declines to answer beyond its sources** rather than hallucinate.

> **Q:** What are the Rasa, Guna, Virya, and Vipaka of Ashwagandha?
> **A:** *"…the provided source passages do not contain information about Ashwagandha… I am unable to provide these properties, as doing so would require generating information not present in the provided texts."*

Rasa Shastra (mineral/metallic) preparations always trigger a supervision warning, and clinical answers close with a qualified-practitioner (Vaidya) disclaimer.

## Demo

```bash
# Full cited answer (requires API keys + credits)
python scripts/demo_query.py --question "What is the Ayurvedic treatment for Amavata?"

# Retrieval + context assembly only — zero API cost
python scripts/dry_run_query.py
```

Returns a structured, cited answer — classical formulations with ingredient tables, doses, and anupāna — each claim tagged `【N】` and traceable to a source document and page.

<!-- Add a terminal screenshot here, e.g.:  ![AyurKosha demo](docs/screenshots/demo_amavata.png) -->

## Tech Stack

- **Python** + **FastAPI** — API layer
- **Claude (Anthropic)** — Query expansion + answer generation
- **Cohere** — Multilingual embeddings + cross-encoder reranking
- **Pinecone** — Vector search
- **BM25 (rank_bm25)** — Keyword search with custom Ayurvedic tokenizer
- **Redis** — Query caching

## Quick Start

```bash
# 1. Clone and setup
git clone https://github.com/logn1602/ayurkosha.git
cd ayurkosha
make setup

# 2. Add your API keys to .env

# 3. Add documents to data/raw/ subdirectories

# 4. Build synonym dictionary
make synonyms

# 5. Run ingestion
make ingest

# 6. Start the server
make serve

# 7. Query
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What is the Ayurvedic treatment for Amavata?"}'
```

## Project Structure

```
ayurkosha/
├── config/          # Settings and logging
├── data/            # Raw docs, synonyms, eval datasets, cache
├── src/
│   ├── ingestion/   # Document loading, chunking, embedding, indexing
│   ├── query/       # Query expansion, HyDE, step-back, filter inference
│   ├── retrieval/   # Semantic search, BM25, RRF fusion
│   ├── reranking/   # Cohere rerank, MMR diversity filtering
│   ├── context/     # Parent expansion, reordering, compression
│   ├── generation/  # Claude prompts, generation, citation verification
│   ├── evaluation/  # Retrieval metrics, generation metrics, LLM judge
│   └── utils/       # Caching, feedback, transliteration
├── api/             # FastAPI endpoints
├── scripts/         # CLI tools for ingestion, evaluation, data prep
└── tests/           # Unit and integration tests
```

## License

MIT
