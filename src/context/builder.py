"""
AyurKosha — Context Block Builder
Assembles the final labeled context block for the generation prompt.

Builds two aligned outputs from the same ordered chunk list: the context
string handed to Claude (with 【N】-numbered sources) and a plain `sources`
list carrying the same numbering — so citation_verify.py can check Claude's
inline 【N】 markers against real sources, and api/routes/query.py can turn
`sources` directly into `SourceInfo` objects for the API response.

Build this in: Phase 4, Step 4
"""

from __future__ import annotations

from typing import Any

_SEPARATOR = "\n---\n"


def _document_label(meta: dict[str, Any]) -> str:
    return meta.get("citation") or meta.get("text_name") or meta.get("source") or "Unknown"


def _section_label(meta: dict[str, Any]) -> str | None:
    heading_path = meta.get("heading_path")
    if heading_path:
        return " > ".join(heading_path)
    return meta.get("sthana")


def build_context(chunks: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Build the labeled context block and parallel source list.

    Args:
        chunks: Ordered chunk dicts (post parent-expansion/reorder), each with
            `text` and `metadata`.

    Returns:
        (context_block, sources) where sources[i] == {"citation_number",
        "document", "page", "heading"} for the chunk at 1-indexed 【i+1】.
    """
    blocks: list[str] = []
    sources: list[dict[str, Any]] = []

    for i, chunk in enumerate(chunks, start=1):
        meta = chunk.get("metadata", {})
        document = _document_label(meta)
        page = meta.get("page")
        heading = _section_label(meta)

        blocks.append(
            f"【Source {i}】\n"
            f"Document: {document}\n"
            f"Page: {page}\n"
            f"Section: {heading or '—'}\n"
            f"Content:\n"
            f"{chunk.get('text', '')}"
        )
        sources.append({
            "citation_number": i,
            "document": document,
            "page": page,
            "heading": heading,
        })

    return _SEPARATOR.join(blocks), sources
