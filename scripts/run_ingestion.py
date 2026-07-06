"""
AyurKosha — Run Ingestion Pipeline
CLI entry point for the full ingestion process.

Run: python scripts/run_ingestion.py
"""

from src.ingestion.pipeline import run_ingestion


if __name__ == "__main__":
    print("AyurKosha — Starting Ingestion Pipeline")
    print("=" * 50)
    run_ingestion(data_dir="data/raw")
