"""
AyurKosha — Answer Generator
Calls Claude API with the assembled context to generate cited answers.

Build this in: Phase 4, Step 6
"""

from __future__ import annotations

from config.settings import settings
from src.generation.prompts import AYURKOSHA_SYSTEM_PROMPT

_client = None

_USER_TEMPLATE = """{context_block}

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


def generate_answer(query: str, context_block: str) -> str:
    """Generate a cited answer for `query` grounded in `context_block`.

    Args:
        query: The user's original question.
        context_block: The 【N】-labeled source passages from
            src/context/builder.py.

    Returns:
        The raw answer text (with inline 【N】 citations), unverified —
        pass through src/generation/citation_verify.py before returning to
        the caller.
    """
    client = _get_client()
    resp = client.messages.create(
        model=settings.generation_model,
        max_tokens=settings.generation_max_tokens,
        system=AYURKOSHA_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": _USER_TEMPLATE.format(context_block=context_block, query=query),
        }],
    )
    return "".join(
        block.text for block in resp.content if getattr(block, "type", None) == "text"
    )
