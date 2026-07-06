"""
AyurKosha — Feedback Endpoint
POST /feedback — Record user feedback.

Build this in: Phase 5
"""

from fastapi import APIRouter

router = APIRouter()


@router.post("/feedback")
async def feedback():
    """Record user feedback for quality monitoring."""
    # TODO: Wire feedback storage
    pass
