"""Tests for src/ingestion/loaders.py.

Uses synthetic fixtures (tmp files) so the suite is fast and does not depend on
the large, gitignored PDFs under data/raw/.
Run: python -m pytest tests/test_loaders.py
"""

from pathlib import Path

from src.ingestion import loaders
from src.ingestion.loaders import (
    normalize_whitespace,
    infer_doc_type,
    load_document,
    load_directory,
)


# ── normalize_whitespace ──────────────────────────────────────────────

def test_normalize_collapses_spaces_and_newlines():
    out = normalize_whitespace("a    b\t\tc")
    assert out == "a b c"


def test_normalize_collapses_blank_lines_and_strips():
    out = normalize_whitespace("  para one\n\n\n\n\npara two   ")
    assert out == "para one\n\npara two"


def test_normalize_handles_carriage_returns():
    assert normalize_whitespace("x\r\ny") == "x\ny"


def test_normalize_empty():
    assert normalize_whitespace("") == ""


# ── infer_doc_type ────────────────────────────────────────────────────

def test_infer_doc_type_from_folder():
    p = Path("data/raw/classical_texts/charaka.pdf")
    assert infer_doc_type(p) == "classical_text"
    p2 = Path("data/raw/pharmacopoeia/api.pdf")
    assert infer_doc_type(p2) == "pharmacopoeia"


def test_infer_doc_type_unknown():
    assert infer_doc_type(Path("somewhere/else/file.pdf")) == "unknown"


# ── load_document dispatch (txt / md / html) ──────────────────────────

def test_load_text_file(tmp_path: Path):
    f = tmp_path / "note.txt"
    f.write_text("Ashwagandha is a Rasayana herb used widely.", encoding="utf-8")
    recs = load_document(f, doc_type="clinical")
    assert len(recs) == 1
    assert "Ashwagandha" in recs[0]["text"]
    assert recs[0]["metadata"]["doc_type"] == "clinical"
    assert recs[0]["metadata"]["source"] == "note.txt"
    assert recs[0]["metadata"]["page"] is None


def test_load_markdown_file(tmp_path: Path):
    f = tmp_path / "doc.md"
    f.write_text("# Heading\n\nGuduchi (Tinospora cordifolia) is immunomodulatory.",
                 encoding="utf-8")
    recs = load_document(f)
    assert len(recs) == 1
    assert "Guduchi" in recs[0]["text"]


def test_load_html_strips_tags(tmp_path: Path):
    f = tmp_path / "page.html"
    f.write_text(
        "<html><head><style>.x{}</style></head>"
        "<body><script>var a=1;</script><p>Haridra is anti-inflammatory.</p></body></html>",
        encoding="utf-8",
    )
    recs = load_document(f)
    assert len(recs) == 1
    assert "Haridra is anti-inflammatory." in recs[0]["text"]
    assert "var a" not in recs[0]["text"]  # script stripped
    assert "{}" not in recs[0]["text"]     # style stripped


def test_tiny_content_dropped(tmp_path: Path):
    f = tmp_path / "blank.txt"
    f.write_text("x", encoding="utf-8")  # below MIN_RECORD_CHARS
    assert load_document(f) == []


def test_unsupported_extension(tmp_path: Path):
    f = tmp_path / "data.xyz"
    f.write_text("some content that is long enough to pass", encoding="utf-8")
    assert load_document(f) == []


def test_missing_file():
    assert load_document(Path("does/not/exist.pdf")) == []


# ── load_directory ────────────────────────────────────────────────────

def test_load_directory_walks_and_tags(tmp_path: Path, monkeypatch):
    # Build a mini data/raw tree.
    ct = tmp_path / "classical_texts"
    ph = tmp_path / "pharmacopoeia"
    ct.mkdir()
    ph.mkdir()
    (ct / "a.txt").write_text("Charaka Samhita passage long enough to keep.",
                              encoding="utf-8")
    (ph / "b.md").write_text("API monograph text long enough to keep.",
                             encoding="utf-8")
    # doc_type is inferred from the folder name regardless of tmp root.
    recs = load_directory(tmp_path)
    assert len(recs) == 2
    types = {r["metadata"]["doc_type"] for r in recs}
    assert types == {"classical_text", "pharmacopoeia"}
