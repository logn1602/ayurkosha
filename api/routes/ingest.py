"""
AyurKosha — Ingestion Endpoint
POST /ingest — Add new documents to the system.

Build this in: Phase 5
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/ingest")
async def ingest():
    """Ingest a new or updated document."""
    # TODO: Wire ingestion pipeline
    pass
