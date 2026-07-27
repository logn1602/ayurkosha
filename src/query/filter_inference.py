"""
AyurKosha — Metadata Filter Inference
Detects department/doc_type/scope from the query for Pinecone filtering.

Narrows semantic search to one doc_type when the query is clearly scoped
(e.g. "What does the Pharmacopoeia say the dose of Triphala Churna is?" ->
pharmacopoeia). Returns None for broad or cross-category queries so retrieval
stays unfiltered — an incorrect filter is worse than no filter, so this fails
safe to None on any error or ambiguity.

Build this in: Phase 4
"""

from __future__ import annotations

import logging

from config.settings import settings

logger = logging.getLogger(__name__)

_client = None

# Canonical doc_type values (see src/ingestion/loaders.py DOC_TYPE_BY_FOLDER).
DOC_TYPES = (
    "classical_text",
    "pharmacopoeia",
    "research_paper",
    "regulatory",
    "clinical",
    "formulation",
)

_CLASSIFICATION_PROMPT = """Classify the following Ayurvedic question into
exactly one category, or "none" if it spans multiple categories or isn't
clearly scoped to just one.

Categories:
- classical_text: questions about classical texts (Charaka Samhita, Sushruta
  Samhita, Ashtanga Hridaya, etc.) or their verses/chapters.
- pharmacopoeia: questions about official drug monographs, identity, purity,
  standard properties (rasa/guna/virya/vipaka) of a single herb/drug.
- research_paper: questions about modern scientific studies/trials/evidence.
- regulatory: questions about regulations, standards, or approvals.
- clinical: questions about clinical practice, patient case management, or
  treatment guidelines.
- formulation: questions about a specific compound formulation (a churna,
  vati, asava, etc.), its ingredients, or how to prepare/dose it.
- none: broad questions, or questions that reasonably span categories.

Respond with ONLY the category name, nothing else.

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


def infer_doc_type_filter(query: str) -> str | None:
    """Classify `query` into a doc_type filter, or None if broad/ambiguous.

    Returns:
        One of DOC_TYPES, or None. Fails safe to None on any API error or
        unrecognized response so an unfiltered search is never blocked.
    """
    query = query.strip()
    if not query:
        return None

    try:
        client = _get_client()
        resp = client.messages.create(
            model=settings.query_expansion_model,
            max_tokens=20,
            messages=[{"role": "user", "content": _CLASSIFICATION_PROMPT.format(query=query)}],
        )
        text = "".join(
            block.text for block in resp.content if getattr(block, "type", None) == "text"
        )
        label = text.strip().lower()
    except Exception as exc:  # noqa: BLE001 — degrade gracefully on any failure
        logger.warning("Filter inference failed (%s); no filter applied.", exc)
        return None

    if label in DOC_TYPES:
        logger.info("Inferred doc_type filter: %s", label)
        return label
    if label != "none":
        logger.debug("Unrecognized doc_type classification %r; no filter applied.", label)
    return None
