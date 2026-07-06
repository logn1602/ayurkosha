# AyurKosha

**The Ayurvedic Knowledge Treasury** — A hybrid search RAG system with verified citations over classical Ayurvedic texts, pharmacopoeia, research literature, and clinical guidelines.

## What It Does

Ask any Ayurvedic question → get a direct, cited answer traceable to the exact source text, chapter, and verse. Every claim is verified. Every formulation includes safety information.

## Architecture

```
Query → Expansion → Semantic + BM25 → RRF Fusion → Cohere Rerank → MMR → Context Assembly → Claude → Citation Verify → Answer
```

**8 RAG patterns:** Hybrid Search, RAG-Fusion, Reranking, Query Transformation, Parent-Child Retrieval, Self-Corrective, Graph (planned), Adaptive (planned).

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
git clone https://github.com/your-username/ayurkosha.git
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
