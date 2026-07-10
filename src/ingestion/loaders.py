"""
AyurKosha — Document Loaders
Reads PDFs, DOCX, Markdown, and HTML into raw text + source metadata.

Each loader returns a list of "records", one per natural unit of the source
(a page for PDFs, the whole file for DOCX/MD/HTML). A record is:

    {
        "text": "<extracted, whitespace-normalized text>",
        "metadata": {
            "source":      "charaka_samhita_pv_sharma.pdf",   # file name
            "source_path": "data/raw/classical_texts/....pdf", # repo-relative
            "doc_type":    "classical_text",                   # inferred
            "page":        12,        # 1-indexed for PDFs, else None
        },
    }

Downstream, metadata.py enriches these records (headings, shloka refs,
monograph fields) and chunkers.py splits/merges them into index units.

Build this in: Phase 2, Step 1
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Project root: src/ingestion/loaders.py -> parents[2].
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Map data/raw/<folder> -> canonical doc_type carried in metadata.
DOC_TYPE_BY_FOLDER = {
    "classical_texts": "classical_text",
    "pharmacopoeia": "pharmacopoeia",
    "research_papers": "research_paper",
    "regulatory": "regulatory",
    "clinical": "clinical",
    "formulations": "formulation",
}

SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".md", ".markdown", ".html", ".htm", ".txt"}

# Records with less than this many characters after cleaning are dropped as
# non-content (blank pages, dividers, page numbers only).
MIN_RECORD_CHARS = 20

_MULTISPACE_RE = re.compile(r"[ \t ]+")
_MULTINEWLINE_RE = re.compile(r"\n{3,}")


def normalize_whitespace(text: str) -> str:
    """Collapse noisy whitespace while preserving paragraph structure.

    - Normalizes line endings to ``\\n``.
    - Collapses runs of spaces/tabs/non-breaking-spaces to a single space.
    - Collapses 3+ blank lines to a single blank line.
    - Strips trailing spaces per line and surrounding whitespace overall.

    NOTE: This cannot repair PDFs whose text layer omits space glyphs (some
    scanned volumes extract words run together, e.g. "wordwordword"). That is a
    source-level defect, not something normalization can recover.
    """
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = _MULTISPACE_RE.sub(" ", text)
    text = "\n".join(line.strip() for line in text.split("\n"))
    text = _MULTINEWLINE_RE.sub("\n\n", text)
    return text.strip()


def infer_doc_type(path: Path) -> str:
    """Infer doc_type from the data/raw subfolder a file lives in.

    Falls back to "unknown" if the file is not under a recognized folder.
    """
    parts = {p.lower() for p in path.parts}
    for folder, doc_type in DOC_TYPE_BY_FOLDER.items():
        if folder in parts:
            return doc_type
    logger.warning("Could not infer doc_type for %s; using 'unknown'.", path)
    return "unknown"


def _rel_path(path: Path) -> str:
    """Return path relative to the project root, using forward slashes."""
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _base_metadata(path: Path, doc_type: str | None) -> dict[str, Any]:
    return {
        "source": path.name,
        "source_path": _rel_path(path),
        "doc_type": doc_type or infer_doc_type(path),
        "page": None,
    }


def load_pdf(
    path: Path,
    doc_type: str | None = None,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Load a PDF into one record per page (1-indexed page numbers).

    Pages that fail to extract or are effectively empty are skipped with a
    warning; a single bad page never aborts the whole document.

    Args:
        max_pages: If set, stop after scanning this many source pages. This
            bounds extraction cost on very large PDFs (extraction is the
            expensive step, so the limit must be applied here, not after).
    """
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError

    try:
        reader = PdfReader(str(path))
    except (PdfReadError, OSError, ValueError) as exc:
        logger.error("Failed to open PDF %s: %s", path, exc)
        return []

    n_pages = len(reader.pages)
    records: list[dict[str, Any]] = []
    for i, page in enumerate(reader.pages, start=1):
        if max_pages is not None and i > max_pages:
            break
        try:
            raw = page.extract_text() or ""
        except Exception as exc:  # pypdf raises assorted errors on bad pages
            logger.warning("PDF %s page %d: extraction failed (%s); skipping.",
                           path.name, i, exc)
            continue
        text = normalize_whitespace(raw)
        if len(text) < MIN_RECORD_CHARS:
            continue
        meta = _base_metadata(path, doc_type)
        meta["page"] = i
        records.append({"text": text, "metadata": meta})

    scanned = min(max_pages, n_pages) if max_pages is not None else n_pages
    logger.info("Loaded %s: %d/%d scanned pages with content (of %d total).",
                path.name, len(records), scanned, n_pages)
    return records


def load_docx(path: Path, doc_type: str | None = None) -> list[dict[str, Any]]:
    """Load a DOCX file into a single record (paragraphs joined by newlines)."""
    try:
        import docx  # python-docx
    except ImportError:
        logger.error("python-docx not installed; cannot load %s.", path.name)
        return []
    try:
        document = docx.Document(str(path))
    except Exception as exc:
        logger.error("Failed to open DOCX %s: %s", path, exc)
        return []
    text = normalize_whitespace("\n".join(p.text for p in document.paragraphs))
    if len(text) < MIN_RECORD_CHARS:
        return []
    return [{"text": text, "metadata": _base_metadata(path, doc_type)}]


def load_html(path: Path, doc_type: str | None = None) -> list[dict[str, Any]]:
    """Load an HTML file into a single record (scripts/styles stripped)."""
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        logger.error("beautifulsoup4 not installed; cannot load %s.", path.name)
        return []
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Failed to read HTML %s: %s", path, exc)
        return []
    soup = BeautifulSoup(raw, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()
    text = normalize_whitespace(soup.get_text(separator="\n"))
    if len(text) < MIN_RECORD_CHARS:
        return []
    return [{"text": text, "metadata": _base_metadata(path, doc_type)}]


def load_text(path: Path, doc_type: str | None = None) -> list[dict[str, Any]]:
    """Load a plain-text or Markdown file into a single record."""
    try:
        raw = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        logger.error("Failed to read text file %s: %s", path, exc)
        return []
    text = normalize_whitespace(raw)
    if len(text) < MIN_RECORD_CHARS:
        return []
    return [{"text": text, "metadata": _base_metadata(path, doc_type)}]


def load_document(
    path: str | Path,
    doc_type: str | None = None,
    max_pages: int | None = None,
) -> list[dict[str, Any]]:
    """Dispatch to the right loader based on file extension.

    Args:
        path: Path to the document.
        doc_type: Override the inferred doc_type (otherwise derived from the
            parent data/raw folder).
        max_pages: PDF-only page cap passed to load_pdf (ignored for other
            formats, which produce a single record).

    Returns:
        List of records (possibly empty if the file is unsupported/unreadable).
    """
    path = Path(path)
    if not path.is_file():
        logger.error("Not a file: %s", path)
        return []

    ext = path.suffix.lower()
    if ext == ".pdf":
        return load_pdf(path, doc_type, max_pages=max_pages)
    if ext == ".docx":
        return load_docx(path, doc_type)
    if ext in (".html", ".htm"):
        return load_html(path, doc_type)
    if ext in (".md", ".markdown", ".txt"):
        return load_text(path, doc_type)

    logger.warning("Unsupported file type %s: %s", ext, path.name)
    return []


def load_directory(
    data_dir: str | Path = None,
    recursive: bool = True,
) -> list[dict[str, Any]]:
    """Load every supported document under a directory (default: data/raw).

    Returns a flat list of records across all files, each tagged with its
    inferred doc_type. Files that yield no content are silently skipped.
    """
    root = Path(data_dir) if data_dir else PROJECT_ROOT / "data" / "raw"
    if not root.is_dir():
        logger.error("Data directory not found: %s", root)
        return []

    pattern = "**/*" if recursive else "*"
    records: list[dict[str, Any]] = []
    n_files = 0
    for path in sorted(root.glob(pattern)):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            continue
        n_files += 1
        records.extend(load_document(path))

    logger.info("Loaded %d records from %d files under %s.",
                len(records), n_files, root)
    return records
