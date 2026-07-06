"""
AyurKosha — Metadata Filter Inference
Detects department/doc_type/scope from the query for Pinecone filtering.

Build this in: Phase 4
"""

# TODO: Implement filter inference
#   - Use Claude to classify query into doc_type
#     (Classical, Pharmacopoeia, Research, Regulatory, Clinical, Formulations)
#   - Return Pinecone metadata filter dict
#   - Return None if query is broad / cross-category
