"""
AyurKosha — Parent-Child Chunk Mapping
Maps small retrieval chunks to their larger parent contexts.

Build this in: Phase 2, Step 8
"""

# TODO: Implement parent-child mapping
#   - For each small chunk, store a mapping to its parent (larger context)
#   - Parent = the full section or ~1500 token window around the chunk
#   - Serialize mapping as JSON for fast lookup
