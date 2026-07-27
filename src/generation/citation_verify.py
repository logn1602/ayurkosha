"""
AyurKosha — Citation Verification
Parses citation markers from generated answers and verifies each one.

Claude is instructed (see src/generation/prompts.py) to cite every claim with
【N】 matching a source number in the context block. This module is the
grounding check: it never trusts a citation number just because Claude wrote
it — every 【N】 is checked against the real `sources` list produced by
src/context/builder.py, and any number outside that range is stripped from
the answer and reported rather than silently left in place.

Build this in: Phase 4, Step 8
"""

from __future__ import annotations

import re
from typing import Any

_CITATION_RE = re.compile(r"【(\d+)】")


def verify_citations(answer: str, sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify and clean 【N】 citation markers in a generated answer.

    Args:
        answer: Raw generated answer text, possibly containing 【N】 markers.
        sources: The sources list from src/context/builder.py — `sources[i]`
            corresponds to citation number `i + 1`.

    Returns:
        {
            "answer": cleaned answer text (hallucinated markers removed),
            "used_sources": sources actually cited, in citation-number order,
            "hallucinated_citations": sorted list of citation numbers that
                appeared in the answer but don't map to a real source,
        }
    """
    valid_numbers = set(range(1, len(sources) + 1))
    used: set[int] = set()
    hallucinated: set[int] = set()

    def _strip_invalid(match: re.Match) -> str:
        n = int(match.group(1))
        if n in valid_numbers:
            used.add(n)
            return match.group(0)
        hallucinated.add(n)
        return ""

    cleaned = _CITATION_RE.sub(_strip_invalid, answer)

    return {
        "answer": cleaned,
        "used_sources": [sources[n - 1] for n in sorted(used)],
        "hallucinated_citations": sorted(hallucinated),
    }
