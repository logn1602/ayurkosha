"""
AyurKosha — Catalog Raw Documents
Scans data/raw/ and produces a manifest of all documents.

Run: python scripts/catalog_data.py
"""

import json
from pathlib import Path

CATEGORIES = {
    "classical_texts": "Classical",
    "pharmacopoeia": "Pharmacopoeia",
    "research_papers": "Research",
    "regulatory": "Regulatory",
    "clinical": "Clinical",
    "formulations": "Formulations",
}

VALID_EXTENSIONS = {".pdf", ".docx", ".md", ".txt", ".html", ".json"}


def catalog():
    manifest = []
    raw_dir = Path("data/raw")

    for category_dir, doc_type in CATEGORIES.items():
        dir_path = raw_dir / category_dir
        if not dir_path.exists():
            continue

        for file_path in dir_path.rglob("*"):
            if file_path.is_file() and file_path.suffix in VALID_EXTENSIONS:
                manifest.append({
                    "path": str(file_path),
                    "filename": file_path.name,
                    "doc_type": doc_type,
                    "format": file_path.suffix,
                    "size_kb": file_path.stat().st_size // 1024,
                    "ingested": False,
                })

    output_path = Path("data/document_manifest.json")
    with open(output_path, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"Cataloged {len(manifest)} documents → {output_path}")
    for doc_type in sorted(set(d["doc_type"] for d in manifest)):
        count = sum(1 for d in manifest if d["doc_type"] == doc_type)
        print(f"  {doc_type}: {count}")

    if not manifest:
        print("\n  No documents found. Add files to data/raw/ subdirectories.")


if __name__ == "__main__":
    catalog()
