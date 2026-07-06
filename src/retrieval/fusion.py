"""
AyurKosha — Reciprocal Rank Fusion
Merges ranked lists from semantic and keyword retrievers.

Build this in: Phase 3, Step 3
"""

# TODO: Implement RRF
#   - RRF score = sum of 1/(k + rank) across all lists
#   - k = 60 (from config)
#   - Sort by fused score descending
#   - Return top_n merged candidates
