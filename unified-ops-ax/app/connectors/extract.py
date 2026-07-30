"""Content extraction with a per-extension registry.

Text formats decode natively. `.docx` is parsed with the stdlib (zipfile +
ElementTree) so no lxml/native deps are needed. `.pdf` uses pypdf (pure
Python). Any extraction failure (corrupt file or a missing optional lib)
returns None and is logged — one bad file never aborts a crawl. Add a format
by registering an extractor in BINARY_EXTRACTORS."""
from __future__ import annotations

import io
import logging
import os
import xml.etree.ElementTree as ET
import zipfile

logger = logging.getLogger(__name__)

TEXT_EXTENSIONS = {".txt", ".md", ".markdown", ".csv", ".tsv", ".json", ".log", ".html", ".htm", ".xml", ".yaml", ".yml"}

_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


class ExtractionError(RuntimeError):
    pass


def _extract_docx(content: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(content)) as zf:
        xml = zf.read("word/document.xml")
    root = ET.fromstring(xml)
    lines: list[str] = []
    # Every paragraph (including those inside table cells) is a w:p of w:t runs.
    for para in root.iter(f"{_W}p"):
        runs = [t.text for t in para.iter(f"{_W}t") if t.text]
        if runs:
            lines.append("".join(runs))
    return "\n".join(lines)


def _extract_pdf(content: bytes) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover - optional dep
        raise ExtractionError("pypdf is required for .pdf extraction") from exc
    reader = PdfReader(io.BytesIO(content))
    pages = [(page.extract_text() or "") for page in reader.pages]
    return "\n".join(pages).strip()


BINARY_EXTRACTORS = {".docx": _extract_docx, ".pdf": _extract_pdf}


def _ext(name: str) -> str:
    return os.path.splitext(name)[1].lower()


def is_extractable(name: str) -> bool:
    ext = _ext(name)
    return ext in TEXT_EXTENSIONS or ext in BINARY_EXTRACTORS


def extract_text(name: str, content: bytes) -> str | None:
    ext = _ext(name)
    if ext in TEXT_EXTENSIONS:
        return content.decode("utf-8", errors="ignore")
    extractor = BINARY_EXTRACTORS.get(ext)
    if extractor is None:
        return None  # unsupported/binary (e.g. image) — skipped
    try:
        return extractor(content)
    except Exception as exc:  # corrupt file or missing optional dep — skip, don't crash
        logger.warning("extraction failed for %s (%s): %s", name, ext, exc)
        return None
