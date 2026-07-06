"""
AyurKosha — Ingestion Pipeline Orchestrator
Wires all ingestion steps into a single run_ingestion() function.

Build this in: Phase 2, Step 9
"""

# TODO: Implement end-to-end pipeline
#   1. Load raw documents from data/raw/
#   2. Extract metadata
#   3. Chunk documents
#   4. Embed all chunks
#   5. Upsert to Pinecone
#   6. Build and save BM25 index
#   7. Build and save parent-child mapping
#   8. Log stats: total docs, total chunks, time taken

def run_ingestion(data_dir: str = "data/raw"):
    """Run the full ingestion pipeline."""
    # TODO: implement
    pass
