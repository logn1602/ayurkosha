"""
AyurKosha — Query Endpoint
POST /query — Main RAG pipeline endpoint.

Build this in: Phase 5
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/query")
async def query():
    """
    Run the full AyurKosha pipeline:
    1. Query expansion
    2. Dual retrieval (semantic + BM25)
    3. Reciprocal Rank Fusion
    4. Cohere reranking + MMR
    5. Context assembly
    6. Claude generation
    7. Citation verification
    8. Return answer + sources
    """
    # TODO: Wire the full pipeline
    pass
