"""
AyurKosha — Run Ingestion Pipeline
CLI entry point for the full ingestion process.

Run (full corpus):        python scripts/run_ingestion.py
Run (cheap validation):   python scripts/run_ingestion.py --max-files 1 --max-pages 40
Dry run (no API cost):    python scripts/run_ingestion.py --no-embed
"""

import argparse
import logging
import sys
from pathlib import Path

# Ensure the project root is importable when this script is run directly
# (python scripts/run_ingestion.py puts scripts/ on sys.path, not the root).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion.pipeline import run_ingestion


def main():
    parser = argparse.ArgumentParser(description="Run the AyurKosha ingestion pipeline.")
    parser.add_argument("--data-dir", default="data/raw", help="Root folder to ingest.")
    parser.add_argument("--max-files", type=int, default=None,
                        help="Process at most N source files.")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="Keep at most N pages per file.")
    parser.add_argument("--no-embed", action="store_true",
                        help="Skip Cohere embedding (build BM25/parent stores only).")
    parser.add_argument("--no-upsert", action="store_true",
                        help="Embed but skip the Pinecone upsert.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    print("AyurKosha — Starting Ingestion Pipeline")
    print("=" * 50)
    stats = run_ingestion(
        data_dir=args.data_dir,
        max_files=args.max_files,
        max_pages=args.max_pages,
        embed=not args.no_embed,
        upsert=not args.no_upsert,
    )
    print("=" * 50)
    print("DONE:", stats)


if __name__ == "__main__":
    main()
