"""
AyurKosha — FastAPI Application
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routes import query, ingest, feedback

app = FastAPI(
    title="AyurKosha",
    description="Ayurvedic Knowledge RAG System — Hybrid Search with Verified Citations",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, tags=["Query"])
app.include_router(ingest.router, tags=["Ingestion"])
app.include_router(feedback.router, tags=["Feedback"])


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ayurkosha"}
