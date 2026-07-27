"""
AyurKosha — Query Endpoint
POST /query — Main RAG pipeline endpoint.

Build this in: Phase 5
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException

from api.dependencies import get_parent_store
from api.schemas import QueryRequest, QueryResponse, SourceInfo
from src.context.builder import build_context
from src.context.parent_expand import expand_to_parents
from src.context.reorder import reorder_chunks
from src.generation.citation_verify import verify_citations
from src.generation.generator import generate_answer
from src.generation.safety import apply_safety_checks
from src.ingestion.parent_store import ParentStore
from src.query.expander import expand_query
from src.query.filter_inference import infer_doc_type_filter
from src.reranking.cohere_rerank import rerank
from src.reranking.mmr import mmr_rerank
from src.retrieval.fusion import reciprocal_rank_fusion
from src.retrieval.keyword import keyword_search
from src.retrieval.semantic import semantic_search

logger = logging.getLogger(__name__)

router = APIRouter()


def run_query_pipeline(request: QueryRequest, parent_store: ParentStore) -> QueryResponse:
    """Run the full AyurKosha pipeline for one query.

    1. Query expansion
    2. Dual retrieval (semantic + BM25)
    3. Reciprocal Rank Fusion
    4. Cohere reranking + MMR
    5. Parent expansion + reading-order sort + context assembly
    6. Claude generation
    7. Citation verification
    8. Safety checks
    """
    doc_type_filter = request.doc_type_filter or infer_doc_type_filter(request.question)
    variants = expand_query(request.question)

    semantic_results = semantic_search(variants, doc_type_filter=doc_type_filter)
    keyword_results = keyword_search(variants)
    fused = reciprocal_rank_fusion([semantic_results, keyword_results])

    reranked = rerank(request.question, fused)
    diverse = mmr_rerank(request.question, reranked, top_k=request.top_k)

    expanded = expand_to_parents(diverse, parent_store)
    ordered = reorder_chunks(expanded)
    context_block, sources = build_context(ordered)

    if not sources:
        raise HTTPException(status_code=404, detail="No relevant sources found for this query.")

    raw_answer = generate_answer(request.question, context_block)
    verified = verify_citations(raw_answer, sources)
    final_answer = apply_safety_checks(verified["answer"], sources)

    return QueryResponse(
        answer=final_answer,
        sources=[SourceInfo(**s) for s in verified["used_sources"]],
        hallucinated_citations=verified["hallucinated_citations"],
        query_variants=variants,
    )


@router.post("/query", response_model=QueryResponse)
async def query(
    request: QueryRequest,
    parent_store: ParentStore = Depends(get_parent_store),
) -> QueryResponse:
    """Run the full AyurKosha pipeline and return a cited answer."""
    try:
        return run_query_pipeline(request, parent_store)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 — surface pipeline failures as 500s
        logger.exception("Query pipeline failed.")
        raise HTTPException(status_code=500, detail=str(exc)) from exc
