"""
AyurKosha — Chunking Strategies
Semantic chunking + structure-aware splitting for Ayurvedic texts.

Build this in: Phase 2, Step 3
This is where you'll spend the most time iterating.
"""

# TODO: Implement two chunking strategies
#   1. SemanticChunker — for general documents
#      Use langchain_experimental.text_splitter.SemanticChunker
#
#   2. Structure-aware chunker — for classical texts
#      Parse heading hierarchy (Sthana > Adhyaya > Verse)
#      Keep each shloka + commentary as a single chunk
#      Carry full heading_path as metadata
#
#   3. Table chunker — for pharmacopoeia monographs
#      Extract tables as standalone chunks
#      Repeat column headers in every chunk
