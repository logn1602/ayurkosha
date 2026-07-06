"""
AyurKosha — Pinecone Storage
Upserts vectors + metadata to Pinecone, handles deletes for updates.

Build this in: Phase 2, Step 6
"""

# TODO: Implement Pinecone operations
#   - create_index() — one-time setup (1024 dims, cosine metric)
#   - upsert_chunks() — batch upsert vectors + metadata
#   - delete_by_source() — delete all chunks from a specific document
#   - Batch upserts in groups of 100 (Pinecone recommendation)
