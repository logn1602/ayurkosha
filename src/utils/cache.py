"""
AyurKosha — Redis Caching Layer
Caches query results to avoid redundant API calls.

Build this in: Phase 7 (after core pipeline works)
"""

# TODO: Implement caching
#   - Cache key = normalized query hash
#   - Cache value = serialized response (answer + sources)
#   - TTL = configurable (e.g., 24 hours)
#   - Invalidate when new documents are ingested
