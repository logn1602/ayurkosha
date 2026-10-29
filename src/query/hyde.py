"""
AyurKosha — HyDE (Hypothetical Document Embeddings)
Generates a hypothetical answer passage, embeds that instead of the query.

A short question ("what helps with joint swelling?") sits far from the
declarative, terminology-dense prose of the source texts in embedding space.
HyDE asks Claude to *write* the kind of passage that would answer the query,
then embeds that passage as a document (input_type="search_document") so it
lands near real passages. The passage only steers dense retrieval — it is
never shown to the generator or cited, so its factual accuracy does not
matter, only its vocabulary and shape.

Best for conceptual queries, not keyword lookups (BM25 still searches the
original query variants unchanged).

Fails safe: on any Claude API error, returns None and retrieval proceeds
without the HyDE vector.

Opt-in (QueryRequest.use_hyde / run_eval.py --hyde), off by default: on the
30-question retrieval eval it *lowered* quality (3 runs each: MRR ~0.63 vs
~0.74, hit_rate ~0.84 vs 0.93). The corpus questions are mostly specific
herb/formulation lookups, where a generic hypothetical passage dilutes the
semantic results rather than sharpening them.

Build this in: Phase 7 (medium priority improvement)
"""

from __future__ import annotations

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None

_HYDE_PROMPT = """Write a short passage (120-180 words) in the style of an
Ayurvedic reference text — a classical treatise, pharmacopoeia monograph, or
clinical manual — that directly answers the question below.

- Use the technical vocabulary such texts use: Sanskrit disease, herb, and
  formulation names, dosha involvement, properties (rasa, guna, virya,
  vipaka), dosage forms, and indications.
- Write declaratively, as the source text would, not as a reply to a user.
- No preamble, no headings, no disclaimers, no citations.

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


def generate_hypothetical_document(query: str) -> str | None:
    """Return a hypothetical source passage answering `query`.

    Args:
        query: The user's original question.

    Returns:
        The generated passage, or None if the query is empty, the response is
        empty, or the Claude call fails.
    """
    query = query.strip()
    if not query:
        return None

    try:
        client = _get_client()
        resp = client.messages.create(
            model=settings.query_expansion_model,
            max_tokens=400,
            messages=[{"role": "user", "content": _HYDE_PROMPT.format(query=query)}],
        )
        passage = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        ).strip()
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any failure
        logger.warning("HyDE generation failed (%s); skipping HyDE vector.", exc)
        return None

    if not passage:
        logger.warning("HyDE returned an empty passage; skipping HyDE vector.")
        return None

    logger.info("HyDE generated a %d-char hypothetical passage.", len(passage))
    return passage
