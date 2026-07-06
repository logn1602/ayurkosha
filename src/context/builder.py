"""
AyurKosha — Context Block Builder
Assembles the final labeled context block for the generation prompt.

Build this in: Phase 4, Step 4
"""

# TODO: Build the context string that gets sent to Claude
#   Format each chunk as:
#     【Source N】
#     Document: {source}
#     Page: {page}
#     Section: {heading_path}
#     Content:
#     {text}
#   Join with "---" separators
