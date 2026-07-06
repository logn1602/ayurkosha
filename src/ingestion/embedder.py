"""
AyurKosha — Embedding Module
Embeds chunks using Cohere with asymmetric input types.

Build this in: Phase 2, Step 5
"""

# TODO: Implement embedding
#   - Use cohere.Client with embed-multilingual-v3.0
#   - Documents: input_type="search_document"
#   - Queries (at search time): input_type="search_query"
#   - Batch embed in groups of 96 (Cohere batch limit)
#   - Handle rate limits with exponential backoff
