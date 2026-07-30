import json
import re

from .encoding import decode_bytes
from .exceptions import ParserException
from .tabular import LAB_VALUE_RE
from .text_cleanup import clean_whitespace

# ── Markdown → plain text ────────────────────────────────────────────────────

_MD_CODE_FENCE_RE = re.compile(r"```[a-zA-Z0-9_+-]*\n(.*?)```", re.DOTALL)
_MD_INLINE_CODE_RE = re.compile(r"`([^`]+)`")
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]*\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]*\)")
_MD_HEADER_RE = re.compile(r"^#{1,6}\s+(.*)$", re.MULTILINE)
_MD_BOLD_ITALIC_RE = re.compile(r"(\*\*\*|___)(.+?)\1")
_MD_BOLD_RE = re.compile(r"(\*\*|__)(.+?)\1")
_MD_ITALIC_RE = re.compile(r"(\*|_)(.+?)\1")
_MD_BLOCKQUOTE_RE = re.compile(r"^>\s?", re.MULTILINE)
_MD_HR_RE = re.compile(r"^\s*([-*_])\1{2,}\s*$", re.MULTILINE)
_MD_LIST_MARKER_RE = re.compile(r"^(\s*)([-*+]|\d+\.)\s+", re.MULTILINE)
_MD_TABLE_SEP_RE = re.compile(r"^\|?[\s:|-]+\|[\s:|-]*$", re.MULTILINE)


def _markdown_to_text(text: str) -> str:
    """Strip markdown syntax down to clean prose while keeping newline
    structure (headers, list items, and blank lines between blocks all
    remain as separate lines). A lightweight regex pass, not a full CommonMark
    parser — good enough for notebook-style research documents.
    """
    text = _MD_CODE_FENCE_RE.sub(lambda m: m.group(1), text)
    text = _MD_INLINE_CODE_RE.sub(lambda m: m.group(1), text)
    text = _MD_IMAGE_RE.sub(lambda m: m.group(1), text)
    text = _MD_LINK_RE.sub(lambda m: m.group(1), text)
    text = _MD_HEADER_RE.sub(lambda m: m.group(1), text)
    text = _MD_BOLD_ITALIC_RE.sub(lambda m: m.group(2), text)
    text = _MD_BOLD_RE.sub(lambda m: m.group(2), text)
    text = _MD_ITALIC_RE.sub(lambda m: m.group(2), text)
    text = _MD_BLOCKQUOTE_RE.sub("", text)
    text = _MD_HR_RE.sub("", text)
    text = _MD_LIST_MARKER_RE.sub(lambda m: f"{m.group(1)}- ", text)
    text = _MD_TABLE_SEP_RE.sub("", text)
    text = re.sub(r"^\|(.*)\|$", lambda m: m.group(1).strip(), text, flags=re.MULTILINE)
    return text


# ── JSON → pretty text + key summary ─────────────────────────────────────────

def _json_to_text(text: str, filename: str) -> str:
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ParserException(f"Invalid JSON in {filename}", file_type="json", original_error=exc) from exc

    if isinstance(data, dict):
        lines = ["Top-level keys:"]
        lines.extend(f"  - {k}: {type(v).__name__}" for k, v in data.items())
        summary = "\n".join(lines)
    elif isinstance(data, list):
        elem_types = sorted({type(v).__name__ for v in data[:200]})
        summary = f"Top-level: a list of {len(data)} items (element types: {', '.join(elem_types) or 'none'})"
    else:
        summary = f"Top-level value type: {type(data).__name__}"

    pretty = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    return f"{summary}\n\n{pretty}"


# ── Lab notebook heuristic ───────────────────────────────────────────────────

_DATE_PATTERN_RE = re.compile(
    r"\b(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|"
    r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{1,2},?\s+\d{4})\b",
    re.IGNORECASE,
)
_RESEARCHER_INDICATOR_RE = re.compile(
    r"\b(recorded by|performed by|signed|signature|investigator|principal investigator|\bPI\b|technician|researcher)\b",
    re.IGNORECASE,
)


def _looks_like_lab_notebook(text: str) -> bool:
    """A rough score: has dates, has measurements (numbers + units), and
    has some indicator of who recorded the entry. Two of three is enough —
    requiring all three is brittle against real notebook formatting.
    """
    score = 0
    if _DATE_PATTERN_RE.search(text):
        score += 1
    if LAB_VALUE_RE.search(text):
        score += 1
    if _RESEARCHER_INDICATOR_RE.search(text):
        score += 1
    return score >= 2


# ── Main entry point ─────────────────────────────────────────────────────────

def extract_text_from_text(file_content: bytes, filename: str) -> dict:
    """Extract and clean text from a plain text / markdown / JSON file."""
    if not file_content:
        raise ParserException("Empty file content", file_type="text")

    raw = decode_bytes(file_content, file_type="text")
    lower_name = filename.lower()

    if lower_name.endswith(".md"):
        text = _markdown_to_text(raw)
        file_kind = "markdown"
    elif lower_name.endswith(".json"):
        text = _json_to_text(raw, filename)
        file_kind = "json"
    else:
        text = raw
        file_kind = "plain"

    text = clean_whitespace(text).strip()

    word_count = len(text.split())
    line_count = len(text.splitlines())
    paragraph_count = len([p for p in re.split(r"\n\s*\n", text) if p.strip()])

    return {
        "text": text,
        "pages": [{"page_number": 1, "text": text, "word_count": word_count}],
        "page_count": 1,
        "word_count": word_count,
        "is_scanned": False,
        "extraction_method": file_kind,
        "metadata": {
            "title": filename,
            "author": None,
            "created_date": None,
            "modified_date": None,
            "line_count": line_count,
            "paragraph_count": paragraph_count,
            "is_lab_notebook_entry": _looks_like_lab_notebook(text),
        },
    }