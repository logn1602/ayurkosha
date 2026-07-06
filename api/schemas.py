"""
AyurKosha — API Request/Response Schemas
"""

from pydantic import BaseModel


class QueryRequest(BaseModel):
    question: str
    doc_type_filter: str | None = None
    use_hyde: bool = False
    top_k: int = 6


class SourceInfo(BaseModel):
    citation_number: int
    document: str
    page: int | None = None
    heading: str | None = None


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceInfo]
    hallucinated_citations: list[int]
    query_variants: list[str]


class IngestRequest(BaseModel):
    file_path: str
    doc_type: str


class IngestResponse(BaseModel):
    status: str
    chunks_created: int


class FeedbackRequest(BaseModel):
    query_id: str
    rating: str  # "up" or "down"
    comment: str | None = None
