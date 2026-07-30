import logging
import os
import re
import tempfile
from collections import Counter
from datetime import datetime
from typing import Optional

import pdfplumber
import pytesseract
from pdf2image import convert_from_path

from .exceptions import ParserException
from .tabular import LAB_UNITS, format_table_as_markdown
from .text_cleanup import clean_whitespace

logger = logging.getLogger("mednotebook.parsers.pdf")

# A scanned page rarely yields more than a stray watermark/page-number via
# pdfplumber's text layer — 100 chars across the first 3 pages combined is a
# generous floor above that noise.
_SCANNED_TEXT_THRESHOLD = 100
_SAMPLE_PAGE_COUNT = 3

# A trailing \b doesn't work after "%" — a non-word char has no boundary
# against adjacent whitespace, so \b would silently fail to match it.
# A lookahead that just rejects a following alnum works for every unit.
_LAB_VALUE_RE = re.compile(rf"(\d+\.?\d*)\s+({LAB_UNITS})(?![A-Za-z0-9])", re.IGNORECASE)
# U+2060 WORD JOINER: invisible and, unlike a non-breaking space, not
# classified as whitespace by str.split()/re \s — so it actually survives
# naive whitespace-based chunking later, which NBSP would not.
_WORD_JOINER = "⁠"

_SECTION_HEADER_RE = re.compile(
    r"^(?:[A-Z][A-Z0-9 /&\-]{2,60}|[A-Za-z][A-Za-z0-9 /&\-]{1,60}:)$"
)

_PDF_DATE_RE = re.compile(r"D:(\d{4})(\d{2})(\d{2})(\d{2})?(\d{2})?(\d{2})?")


def is_scanned_pdf(pdf_path: str) -> bool:
    """Heuristic: a PDF is "scanned" if its text layer is essentially empty.

    Samples the first few pages rather than the whole document so this stays
    cheap even for long PDFs.
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            sample = pdf.pages[:_SAMPLE_PAGE_COUNT]
            extracted = "".join((page.extract_text() or "") for page in sample)
    except Exception as exc:
        raise ParserException("Could not open PDF to inspect its contents", file_type="pdf", original_error=exc) from exc

    return len(extracted.strip()) < _SCANNED_TEXT_THRESHOLD


def extract_text_from_pdf(file_content: bytes) -> dict:
    """Extract text, tables, and metadata from a PDF's raw bytes.

    Uses pdfplumber for text-based PDFs and falls back to Tesseract OCR
    (via pdf2image) for scanned ones. Raises ParserException if nothing
    usable could be extracted either way.
    """
    if not file_content:
        raise ParserException("Empty file content", file_type="pdf")

    tmp_path = _write_temp_pdf(file_content)
    try:
        metadata, page_count = _read_pdf_info(tmp_path)
        scanned = is_scanned_pdf(tmp_path)

        pages: list[dict] = []
        extraction_method = "pdfplumber"

        if not scanned:
            pages = _extract_with_pdfplumber(tmp_path)
            if not any(p["text"].strip() for p in pages):
                # Text layer existed but yielded nothing usable (e.g. an
                # image-only page mixed with a near-empty cover page) — OCR it.
                scanned = True

        if scanned:
            extraction_method = "tesseract"
            pages = _extract_with_tesseract(tmp_path)

        if not pages or not any(p["text"].strip() for p in pages):
            raise ParserException(
                f"No text could be extracted from PDF (page_count={page_count}, is_scanned={scanned})",
                file_type="pdf",
            )

        pages = _strip_repeated_headers_footers(pages)
        pages = [_finalize_page(p) for p in pages]

        full_text = "\n\n".join(p["text"] for p in pages)
        word_count = sum(p["word_count"] for p in pages)

        return {
            "text": full_text,
            "pages": pages,
            "page_count": page_count,
            "word_count": word_count,
            "is_scanned": scanned,
            "extraction_method": extraction_method,
            "metadata": metadata,
        }
    finally:
        os.unlink(tmp_path)


# ── Temp file / PDF info ────────────────────────────────────────────────────

def _write_temp_pdf(file_content: bytes) -> str:
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(file_content)
        return tmp.name


def _read_pdf_info(pdf_path: str) -> tuple[dict, int]:
    try:
        with pdfplumber.open(pdf_path) as pdf:
            return _extract_metadata(pdf), len(pdf.pages)
    except Exception as exc:
        raise ParserException("Could not open PDF", file_type="pdf", original_error=exc) from exc


def _extract_metadata(pdf: "pdfplumber.PDF") -> dict:
    raw = pdf.metadata or {}
    return {
        "title": raw.get("Title") or None,
        "author": raw.get("Author") or None,
        "created_date": _parse_pdf_date(raw.get("CreationDate")),
        "modified_date": _parse_pdf_date(raw.get("ModDate")),
    }


def _parse_pdf_date(raw: Optional[str]) -> Optional[str]:
    if not raw:
        return None
    raw = raw.strip()
    match = _PDF_DATE_RE.match(raw)
    if not match:
        return raw or None
    year, month, day, hour, minute, second = match.groups()
    try:
        dt = datetime(int(year), int(month), int(day), int(hour or 0), int(minute or 0), int(second or 0))
        return dt.isoformat()
    except ValueError:
        return raw


# ── Extraction backends ─────────────────────────────────────────────────────

def _extract_with_pdfplumber(pdf_path: str) -> list[dict]:
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages, start=1):
            try:
                tables = page.find_tables()
            except Exception as exc:
                logger.warning("table detection failed on page %d: %s", i, exc)
                tables = []

            # Exclude each detected table's bounding box before extracting
            # prose, so table cell contents aren't duplicated verbatim
            # (and jumbled) in the surrounding paragraph text.
            prose_source = page
            for table in tables:
                try:
                    prose_source = prose_source.outside_bbox(table.bbox)
                except Exception as exc:
                    logger.warning("could not exclude table bbox on page %d: %s", i, exc)

            prose = (prose_source.extract_text() or "").strip()

            table_blocks = []
            for table in tables:
                try:
                    markdown = format_table_as_markdown(table.extract())
                except Exception as exc:
                    logger.warning("table extraction failed on page %d: %s", i, exc)
                    continue
                if markdown:
                    table_blocks.append(markdown)

            page_text = prose
            if table_blocks:
                page_text = (page_text + "\n\n" + "\n\n".join(table_blocks)).strip()

            pages.append({"page_number": i, "text": page_text})
    return pages


def _extract_with_tesseract(pdf_path: str) -> list[dict]:
    try:
        images = convert_from_path(pdf_path, dpi=300)
    except Exception as exc:
        raise ParserException(
            "Could not render PDF pages to images for OCR — is poppler installed? (brew install poppler)",
            file_type="pdf",
            original_error=exc,
        ) from exc

    pages = []
    for i, image in enumerate(images, start=1):
        try:
            text = pytesseract.image_to_string(image)
        except Exception as exc:
            raise ParserException(
                f"OCR failed on page {i} — is tesseract installed? (brew install tesseract)",
                file_type="pdf",
                original_error=exc,
            ) from exc
        pages.append({"page_number": i, "text": text.strip()})
    return pages


# ── Headers / footers ───────────────────────────────────────────────────────

def _strip_repeated_headers_footers(pages: list[dict]) -> list[dict]:
    """Blank out a page's first/last line if that exact line repeats across
    most pages — a running header or footer. Only the matched line is
    removed; everything else (including blank lines) is left untouched so
    paragraph breaks survive.
    """
    if len(pages) < _SAMPLE_PAGE_COUNT:
        return pages

    raw_lines = [page["text"].splitlines() for page in pages]

    first_lines: Counter = Counter()
    last_lines: Counter = Counter()
    for lines in raw_lines:
        i = _first_nonblank_index(lines)
        j = _last_nonblank_index(lines)
        if i is not None:
            first_lines[lines[i].strip()] += 1
        if j is not None:
            last_lines[lines[j].strip()] += 1

    threshold = max(3, len(pages) // 2 + 1)
    header_candidates = {ln for ln, count in first_lines.items() if ln and count >= threshold}
    footer_candidates = {ln for ln, count in last_lines.items() if ln and count >= threshold}

    if not header_candidates and not footer_candidates:
        return pages

    cleaned = []
    for page, lines in zip(pages, raw_lines):
        lines = list(lines)
        i = _first_nonblank_index(lines)
        if i is not None and lines[i].strip() in header_candidates:
            lines[i] = ""
        j = _last_nonblank_index(lines)
        if j is not None and lines[j].strip() in footer_candidates:
            lines[j] = ""
        cleaned.append({**page, "text": "\n".join(lines)})
    return cleaned


def _first_nonblank_index(lines: list) -> Optional[int]:
    for i, ln in enumerate(lines):
        if ln.strip():
            return i
    return None


def _last_nonblank_index(lines: list) -> Optional[int]:
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip():
            return i
    return None


# ── Per-page cleanup ─────────────────────────────────────────────────────────

def _finalize_page(page: dict) -> dict:
    text = clean_whitespace(page["text"])
    text = _protect_lab_values(text)
    text = _preserve_section_headers(text)
    text = text.strip()
    return {
        "page_number": page["page_number"],
        "text": text,
        "word_count": len(text.split()),
    }


def _protect_lab_values(text: str) -> str:
    return _LAB_VALUE_RE.sub(lambda m: f"{m.group(1)}{_WORD_JOINER}{m.group(2)}", text)


def _preserve_section_headers(text: str) -> str:
    """Best-effort: surround likely section headers (ALL CAPS lines, or
    short lines ending in ':') with blank lines so later paragraph-based
    chunking treats them as their own block instead of merging them into
    adjacent prose. Heuristic — there's no ground truth in raw extracted text.
    """
    lines = text.split("\n")
    out: list[str] = []
    for idx, line in enumerate(lines):
        stripped = line.strip()
        if stripped and _SECTION_HEADER_RE.match(stripped):
            if out and out[-1].strip():
                out.append("")
            out.append(stripped)
            if idx + 1 < len(lines) and lines[idx + 1].strip():
                out.append("")
        else:
            out.append(line)
    return "\n".join(out)