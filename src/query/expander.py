"""
AyurKosha — Query Expansion
Rewrites user queries into multiple alternative phrasings using Claude.

Broadens recall for hybrid retrieval: a layperson's phrasing ("joint pain and
swelling") often misses the classical/technical vocabulary ("Amavata",
"Sandhivata") the source texts actually use. Each variant is searched
separately by semantic + keyword retrieval and merged (see
src/retrieval/semantic.py, src/retrieval/keyword.py), so more variants ==
more recall at the cost of more retrieval calls.

Fails safe: on any Claude API error, returns just the original query so
retrieval always has at least one variant to search.

Build this in: Phase 4 (or earlier for better retrieval)
"""

from __future__ import annotations

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None

_EXPANSION_PROMPT = """You expand Ayurvedic health questions into alternative
phrasings to widen search recall over classical texts, pharmacopoeia, and
clinical literature.

Given the user's question, write 3-4 alternative phrasings that:
- Include formal/classical Ayurvedic terminology where applicable (Sanskrit
  disease and herb names, e.g. "Amavata" for "joint pain with stiffness").
- Include plain modern medical phrasing where applicable.
- Preserve the original meaning — do not introduce new constraints.

Return ONLY the alternative phrasings, one per line, with no numbering, no
labels, and no extra commentary.

Question: {query}"""


def _get_client():
    """Lazily construct and cache the Anthropic client."""
    global _client
    if _client is not None:
        return _client
    import anthropic

    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set.")
    _client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    return _client


def expand_query(query: str) -> list[str]:
    """Return the original query plus 3-4 alternative phrasings.

    Args:
        query: The user's original question.

    Returns:
        A list starting with `query`, followed by deduplicated alternative
        phrasings. On any API error, returns `[query]` unchanged.
    """
    query = query.strip()
    if not query:
        return []

    try:
        client = _get_client()
        resp = client.messages.create(
            model=settings.query_expansion_model,
            max_tokens=300,
            messages=[{"role": "user", "content": _EXPANSION_PROMPT.format(query=query)}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        variants = [line.strip() for line in text.splitlines() if line.strip()]
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any failure
        logger.warning("Query expansion failed (%s); using original query only.", exc)
        return [query]

    seen = {query.lower()}
    result = [query]
    for variant in variants:
        key = variant.lower()
        if key not in seen:
            seen.add(key)
            result.append(variant)

    logger.info("Expanded query into %d variant(s).", len(result))
    return result
