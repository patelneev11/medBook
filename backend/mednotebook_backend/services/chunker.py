import logging
import re
from dataclasses import dataclass
from typing import Optional

import tiktoken

logger = logging.getLogger("mednotebook.chunker")

_ENCODING = tiktoken.get_encoding("cl100k_base")

# Exactly the pattern specified for this chunker — narrower than the
# broader unit list used elsewhere in the parsers (services/parsers/tabular.py).
LAB_VALUE_RE = re.compile(r"\d+\.?\d*\s*(mg/dL|mmol/L|IU/L|%|g/L)")

_MD_HEADER_RE = re.compile(r"^#{1,6}\s+.+$")
_TABLE_ROW_RE = re.compile(r"^\s*\|.*\|\s*$")
_LIST_ITEM_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
_BLANK_LINE_RE = re.compile(r"\n[ \t]*\n[ \t\n]*")
# ". "/"? "/"! " followed by a capital letter, per spec's "simple sentence
# boundary detection". Deliberately naive — a decimal like "7.2" never has
# a space after the period, so it's never mistaken for a sentence break.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+(?=[A-Z])")
# A sentence ending in a bare number followed by one starting with a unit —
# e.g. "...measured 126" | "mg/dL was recorded..." — glued back together so
# a lab value is never separated from its unit by a chunk boundary.
_TRAILING_NUMBER_RE = re.compile(r"\d$")
_LEADING_UNIT_RE = re.compile(r"^(mg/dL|mmol/L|IU/L|g/L|mEq/L|mmHg|bpm|%)", re.IGNORECASE)


@dataclass
class ChunkingConfig:
    max_chunk_tokens: int = 512
    min_chunk_tokens: int = 50
    overlap_tokens: int = 64
    respect_sentences: bool = True
    respect_paragraphs: bool = True


def count_tokens(text: str) -> int:
    return len(_ENCODING.encode(text))


def chunk_text(text: str, config: ChunkingConfig, page_number: Optional[int] = None) -> list:
    """Split text into semantically-bounded chunks for embedding/retrieval.

    Splits at paragraph/header/table/list boundaries first, only falling
    back to sentence-level splitting for sections too large to keep whole.
    Tables are never split. Overlap is applied within a section that itself
    gets split into multiple chunks, not across unrelated sections — each
    top-level section starts clean (see the docstring on _chunk_block).
    """
    if not text or not text.strip():
        return []

    blocks = _split_into_blocks(text, config)
    raw_chunks = []
    for block in blocks:
        raw_chunks.extend(_chunk_block(block, config))

    chunks = _merge_small_chunks(raw_chunks, config)

    for i, chunk in enumerate(chunks):
        chunk["chunk_index"] = i
        chunk["metadata"]["page_number"] = page_number

    return chunks


# ── Section / block splitting ────────────────────────────────────────────────

def _split_into_blocks(text: str, config: ChunkingConfig) -> list:
    spans = _find_blank_line_spans(text) if config.respect_paragraphs else [(0, len(text))]

    blocks = []
    for start, end in spans:
        block_text = text[start:end]
        if not block_text.strip():
            continue
        blocks.extend(_split_block_headers(block_text, start))

    if not config.respect_paragraphs:
        blocks = _merge_adjacent_paragraphs(blocks)

    return blocks


def _find_blank_line_spans(text: str) -> list:
    spans = []
    pos = 0
    for m in _BLANK_LINE_RE.finditer(text):
        if m.start() > pos:
            spans.append((pos, m.start()))
        pos = m.end()
    if pos < len(text):
        spans.append((pos, len(text)))
    return spans


def _merge_adjacent_paragraphs(blocks: list) -> list:
    """Used only when respect_paragraphs=False: soften blank-line breaks
    between plain paragraphs while still never merging across a table,
    list, or header — those stay protected unconditionally.
    """
    merged = []
    for block in blocks:
        if merged and merged[-1]["kind"] == "paragraph" and block["kind"] == "paragraph":
            prev = merged[-1]
            prev["text"] = prev["text"] + "\n\n" + block["text"]
            prev["char_end"] = block["char_end"]
        else:
            merged.append(dict(block))
    return merged


def _split_block_headers(block_text: str, base_offset: int) -> list:
    """Peel a leading markdown/ALL-CAPS header line off a block even when
    there's no blank line separating it from its body (some parser output
    doesn't guarantee one).
    """
    first_line = block_text.split("\n", 1)[0]
    if not _is_header_line(first_line.strip()):
        return [{
            "text": block_text,
            "kind": _classify_block(block_text),
            "char_start": base_offset,
            "char_end": base_offset + len(block_text),
        }]

    header_block = {
        "text": first_line.strip(),
        "kind": "header",
        "char_start": base_offset,
        "char_end": base_offset + len(first_line),
    }
    remainder_start = len(first_line) + 1  # skip the newline
    if remainder_start >= len(block_text):
        return [header_block]

    remainder_text = block_text[remainder_start:]
    if not remainder_text.strip():
        return [header_block]

    remainder_block = {
        "text": remainder_text,
        "kind": _classify_block(remainder_text),
        "char_start": base_offset + remainder_start,
        "char_end": base_offset + remainder_start + len(remainder_text),
    }
    return [header_block, remainder_block]


def _is_header_line(line: str) -> bool:
    if not line or len(line) > 80:
        return False
    if _MD_HEADER_RE.match(line):
        return True
    if _TABLE_ROW_RE.match(line) or _LIST_ITEM_RE.match(line):
        return False
    letters = [c for c in line if c.isalpha()]
    if len(letters) < 2:
        return False
    upper_ratio = sum(1 for c in letters if c.isupper()) / len(letters)
    return upper_ratio >= 0.9


def _classify_block(text: str) -> str:
    lines = [ln for ln in text.split("\n") if ln.strip()]
    if not lines:
        return "paragraph"
    if all(_TABLE_ROW_RE.match(ln) for ln in lines):
        return "table"
    list_lines = sum(1 for ln in lines if _LIST_ITEM_RE.match(ln))
    if list_lines / len(lines) >= 0.5:
        return "list"
    return "paragraph"


# ── Per-block chunking ───────────────────────────────────────────────────────

def _chunk_block(block: dict, config: ChunkingConfig) -> list:
    """Turn one block into one or more chunks. Overlap only ever applies
    *within* the chunks produced here (a single oversized section split
    into pieces) — it does not carry across separate top-level blocks,
    matching the spec's "for each section" framing.
    """
    text, kind = block["text"], block["kind"]
    tokens = count_tokens(text)

    if kind == "table":
        if tokens > config.max_chunk_tokens * 1.5:
            logger.info("table chunk is %d tokens, over 150%% of max_chunk_tokens — kept whole anyway", tokens)
        return [_make_chunk(text, "table", block["char_start"], block["char_end"], tokens)]

    if kind == "header":
        # Tentatively standalone; _merge_small_chunks will normally fold
        # this into the section that follows, producing "header+content".
        return [_make_chunk(text, "header+content", block["char_start"], block["char_end"], tokens)]

    if tokens <= config.max_chunk_tokens:
        chunk_type = "list" if kind == "list" else "paragraph"
        return [_make_chunk(text, chunk_type, block["char_start"], block["char_end"], tokens)]

    if kind == "list":
        units = _split_list_items(text, block["char_start"])
        return _accumulate_units(units, config, "list")

    if config.respect_sentences:
        units = _merge_split_lab_values(_split_sentences(text, block["char_start"]))
    else:
        units = _split_fixed_token_windows(text, block["char_start"], config.max_chunk_tokens)
    return _accumulate_units(units, config, "paragraph")


def _make_chunk(text: str, chunk_type: str, char_start: int, char_end: int, token_count: int) -> dict:
    return {
        "chunk_index": None,  # filled in by chunk_text once the full list is known
        "content": text,
        "token_count": token_count,
        "char_start": char_start,
        "char_end": char_end,
        "chunk_type": chunk_type,
        "metadata": {
            "contains_table": chunk_type == "table",
            "contains_lab_values": bool(LAB_VALUE_RE.search(text)),
            "is_header": _is_header_line(text.split("\n", 1)[0].strip()),
            "page_number": None,  # filled in by chunk_text
        },
    }


# ── Sentence / list-item splitting ──────────────────────────────────────────

def _split_sentences(text: str, base_offset: int) -> list:
    boundaries = [0]
    for m in _SENTENCE_SPLIT_RE.finditer(text):
        boundaries.append(m.start())
        boundaries.append(m.end())
    boundaries.append(len(text))

    units = []
    for i in range(0, len(boundaries) - 1, 2):
        start, end = boundaries[i], boundaries[i + 1]
        sentence = text[start:end]
        if sentence.strip():
            units.append({"text": sentence, "char_start": base_offset + start, "char_end": base_offset + end})
    return units


def _merge_split_lab_values(units: list) -> list:
    merged = []
    i = 0
    while i < len(units):
        current = units[i]
        if (
            i + 1 < len(units)
            and _TRAILING_NUMBER_RE.search(current["text"].rstrip())
            and _LEADING_UNIT_RE.match(units[i + 1]["text"].lstrip())
        ):
            nxt = units[i + 1]
            merged.append({
                "text": current["text"] + " " + nxt["text"],
                "char_start": current["char_start"],
                "char_end": nxt["char_end"],
            })
            i += 2
        else:
            merged.append(current)
            i += 1
    return merged


def _split_list_items(text: str, base_offset: int) -> list:
    """One unit per list item, including any wrapped continuation lines
    that follow it without their own marker — never split mid-item.
    """
    lines = text.split("\n")
    units = []
    cursor = 0
    item_start = None
    item_lines = []

    for line in lines:
        if _LIST_ITEM_RE.match(line):
            if item_lines:
                item_text = "\n".join(item_lines)
                units.append({"text": item_text, "char_start": base_offset + item_start, "char_end": base_offset + item_start + len(item_text)})
            item_start = cursor
            item_lines = [line]
        elif item_lines:
            item_lines.append(line)
        cursor += len(line) + 1  # +1 for the newline consumed by split("\n")

    if item_lines:
        item_text = "\n".join(item_lines)
        units.append({"text": item_text, "char_start": base_offset + item_start, "char_end": base_offset + item_start + len(item_text)})
    return units


def _split_fixed_token_windows(text: str, base_offset: int, window_tokens: int) -> list:
    """Fallback for respect_sentences=False: fixed token-count windows with
    no regard for sentence boundaries. Char offsets are approximate here —
    decode(encode(text)) isn't always byte-identical to the source text.
    """
    token_ids = _ENCODING.encode(text)
    units = []
    cursor_char = 0
    for i in range(0, len(token_ids), max(1, window_tokens)):
        window_text = _ENCODING.decode(token_ids[i:i + window_tokens])
        start_char = cursor_char
        end_char = start_char + len(window_text)
        units.append({"text": window_text, "char_start": base_offset + start_char, "char_end": base_offset + end_char})
        cursor_char = end_char
    return units


# ── Greedy accumulation with overlap ─────────────────────────────────────────

def _accumulate_units(units: list, config: ChunkingConfig, base_type: str) -> list:
    if not units:
        return []

    join_sep = " " if base_type == "paragraph" else "\n"
    chunks: list = []
    current_texts: list = []
    current_tokens = 0
    current_start = units[0]["char_start"]
    current_end = current_start

    def flush_current():
        if not current_texts:
            return
        content = join_sep.join(current_texts)
        chunks.append(_make_chunk(content, base_type, current_start, current_end, count_tokens(content)))

    for unit in units:
        unit_tokens = count_tokens(unit["text"])

        if current_texts and current_tokens + unit_tokens > config.max_chunk_tokens:
            flush_current()
            overlap_text = (
                _take_last_tokens(chunks[-1]["content"], config.overlap_tokens)
                if config.overlap_tokens > 0 else ""
            )
            current_texts = [overlap_text] if overlap_text else []
            current_tokens = count_tokens(overlap_text) if overlap_text else 0
            current_start = unit["char_start"]
            current_end = current_start

        if not current_texts:
            current_start = unit["char_start"]

        current_texts.append(unit["text"])
        current_tokens += unit_tokens
        current_end = unit["char_end"]

    flush_current()
    return chunks


def _take_last_tokens(text: str, n: int) -> str:
    token_ids = _ENCODING.encode(text)
    if len(token_ids) <= n:
        return text
    return _ENCODING.decode(token_ids[-n:])


# ── Small-chunk merging ──────────────────────────────────────────────────────

def _merge_small_chunks(chunks: list, config: ChunkingConfig) -> list:
    """Fold undersized chunks into a neighbor rather than leaving tiny
    isolated chunks — this is also what turns a standalone header chunk
    plus its following section into one "header+content" chunk. Tables are
    never a merge source or target, preserving their isolation.
    """
    if not chunks:
        return chunks

    merged: list = []
    i = 0
    while i < len(chunks):
        current = chunks[i]
        if current["chunk_type"] == "table" or current["token_count"] >= config.min_chunk_tokens:
            merged.append(current)
            i += 1
            continue

        if i + 1 < len(chunks) and chunks[i + 1]["chunk_type"] != "table":
            chunks[i + 1] = _combine(current, chunks[i + 1])
            i += 1
            continue

        if merged and merged[-1]["chunk_type"] != "table":
            prev = merged.pop()
            merged.append(_combine(prev, current))
        else:
            merged.append(current)
        i += 1

    return merged


def _combine(first: dict, second: dict) -> dict:
    combined_type = first["chunk_type"] if first["chunk_type"] == "header+content" else second["chunk_type"]
    content = first["content"] + "\n\n" + second["content"]
    return _make_chunk(content, combined_type, first["char_start"], second["char_end"], count_tokens(content))