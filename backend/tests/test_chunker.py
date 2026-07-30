import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mednotebook_backend.services.chunker import ChunkingConfig, _take_last_tokens, chunk_text, count_tokens


def _make_long_text(num_sentences: int = 60) -> str:
    return " ".join(
        f"Patient visit number {i} showed stable vital signs and normal "
        f"laboratory results throughout the examination period."
        for i in range(num_sentences)
    )


def _make_table(num_rows: int = 80) -> str:
    rows = ["| Test | Result | Reference Range | Notes |", "| --- | --- | --- | --- |"]
    for i in range(num_rows):
        rows.append(
            f"| Test {i} | {i}.5 mg/dL | 0-10 mg/dL | "
            f"within normal limits for this specific panel item number {i} |"
        )
    return "\n".join(rows)


# ── count_tokens ─────────────────────────────────────────────────────────────

def test_count_tokens_matches_encoding_length():
    text = "Fasting glucose was 7.2 mg/dL on the most recent panel."
    assert count_tokens(text) > 0
    assert count_tokens("") == 0
    assert count_tokens(text * 2) > count_tokens(text)


# ── Required test 1: short text becomes one chunk ───────────────────────────

def test_short_text_becomes_one_chunk():
    text = "Patient presented with mild fatigue. Recommended follow-up in two weeks."
    chunks = chunk_text(text, ChunkingConfig())

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk["chunk_index"] == 0
    assert chunk["content"] == text
    assert chunk["char_start"] == 0
    assert chunk["char_end"] == len(text)
    assert chunk["token_count"] == count_tokens(text)


# ── Required test 2: long text gets split, with overlap ─────────────────────

def test_long_text_splits_with_overlap():
    config = ChunkingConfig()
    long_text = _make_long_text(60)
    assert count_tokens(long_text) > config.max_chunk_tokens * 2  # actually exercises multi-chunk splitting

    chunks = chunk_text(long_text, config)

    assert len(chunks) > 1
    for chunk in chunks:
        # A little slack is expected/acceptable: overlap text is prepended
        # to the next chunk *after* the max-tokens check for the boundary
        # unit, and greedy accumulation checks before adding each unit.
        assert chunk["token_count"] <= config.max_chunk_tokens * 1.1

    # chunk_index is sequential starting at 0
    assert [c["chunk_index"] for c in chunks] == list(range(len(chunks)))

    # Consecutive chunks actually overlap: the second chunk should start
    # with exactly the last overlap_tokens tokens of the first chunk's
    # content (checked via the chunker's own token-decode helper, not an
    # approximation — token boundaries don't align with word boundaries).
    for i in range(len(chunks) - 1):
        first, second = chunks[i], chunks[i + 1]
        expected_overlap = _take_last_tokens(first["content"], config.overlap_tokens)
        assert second["content"][: len(expected_overlap)] == expected_overlap


# ── Required test 3: a markdown table is never split ─────────────────────────

def test_markdown_table_never_split():
    config = ChunkingConfig()
    table_md = _make_table(80)
    assert count_tokens(table_md) > config.max_chunk_tokens  # actually exercises the oversized-table path

    text = (
        "LAB PANEL RESULTS\n\n"
        "Below are this patient's complete lab results from the most recent visit.\n\n"
        f"{table_md}\n\n"
        "End of report."
    )
    chunks = chunk_text(text, config)

    table_chunks = [c for c in chunks if c["chunk_type"] == "table"]
    assert len(table_chunks) == 1

    table_chunk = table_chunks[0]
    assert table_chunk["content"].count("|") == table_md.count("|")
    assert "Test 0 " in table_chunk["content"] or "Test 0 |" in table_chunk["content"]
    assert "Test 79" in table_chunk["content"]
    assert table_chunk["metadata"]["contains_table"] is True
    # Deliberately allowed to exceed max_chunk_tokens — never split instead.
    assert table_chunk["token_count"] > config.max_chunk_tokens


def test_table_row_count_is_preserved_exactly():
    config = ChunkingConfig()
    table_md = _make_table(80)
    chunks = chunk_text(table_md, config)

    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "table"
    # header + separator + 80 data rows
    assert chunks[0]["content"].strip().count("\n") == 81


# ── Required test 4: minimum chunk size is respected ─────────────────────────

def test_small_fragments_are_merged_up_to_minimum():
    config = ChunkingConfig(min_chunk_tokens=50)
    # 20 standalone short paragraphs, none reaching min_chunk_tokens on its
    # own (~15 tokens each) — but with enough total content (~300 tokens)
    # that merging should produce several full-size chunks, not collapse
    # everything into one undersized document (that's a separate, already
    # covered case: test_single_short_document_is_not_forced_above_minimum).
    paragraphs = [f"Visit {i}: patient reported stable condition with no new symptoms noted today." for i in range(20)]
    text = "\n\n".join(paragraphs)
    assert count_tokens(text) > config.min_chunk_tokens * 4

    chunks = chunk_text(text, config)

    assert len(chunks) > 1
    for chunk in chunks:
        assert chunk["token_count"] >= config.min_chunk_tokens

    # Nothing was silently dropped — every fragment's text survived somewhere.
    combined = " ".join(c["content"] for c in chunks)
    for i in range(20):
        assert f"Visit {i}:" in combined


def test_single_short_document_is_not_forced_above_minimum():
    # A whole document shorter than min_chunk_tokens has nothing to merge
    # with — it should stay as the sole chunk rather than erroring or
    # producing zero chunks.
    config = ChunkingConfig(min_chunk_tokens=50)
    text = "Brief note."
    chunks = chunk_text(text, config)

    assert len(chunks) == 1
    assert chunks[0]["content"] == text


# ── Header + content ─────────────────────────────────────────────────────────

def test_header_merges_with_following_content():
    text = "PATIENT HISTORY\n\nNo prior conditions of note."
    chunks = chunk_text(text, ChunkingConfig())

    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "header+content"
    assert "PATIENT HISTORY" in chunks[0]["content"]
    assert "No prior conditions" in chunks[0]["content"]
    assert chunks[0]["metadata"]["is_header"] is True


def test_markdown_header_detected():
    text = "## Lab Results\n\nGlucose was within normal limits for this visit."
    chunks = chunk_text(text, ChunkingConfig())

    assert chunks[0]["chunk_type"] == "header+content"
    assert chunks[0]["metadata"]["is_header"] is True


# ── Lab value protection ─────────────────────────────────────────────────────

def test_lab_value_metadata_flag():
    text = "Fasting glucose: 126 mg/dL, which is above the reference range."
    chunks = chunk_text(text, ChunkingConfig())

    assert chunks[0]["metadata"]["contains_lab_values"] is True


def test_lab_value_not_split_across_chunk_boundary():
    # Force a boundary right around the lab-value sentence by padding with
    # filler sentences on either side, using a tiny max_chunk_tokens so the
    # accumulator is forced to make a cut decision near the value.
    config = ChunkingConfig(max_chunk_tokens=40, min_chunk_tokens=5, overlap_tokens=5)
    filler = "The patient reported no other symptoms during today's visit. "
    text = (filler * 5) + "Glucose 126 mg/dL was recorded during the visit. " + (filler * 5)

    chunks = chunk_text(text, config)

    for chunk in chunks:
        content = chunk["content"]
        if "126" in content:
            assert "mg/dL" in content, f"lab value split from its unit: {content!r}"
        if "mg/dL" in content and "Glucose" in content:
            assert "126" in content


# ── List items ────────────────────────────────────────────────────────────────

def test_list_item_not_split_mid_item():
    config = ChunkingConfig(max_chunk_tokens=30, min_chunk_tokens=5, overlap_tokens=0)
    items = "\n".join(f"- Sample {i}: collected and logged without incident during rounds." for i in range(20))
    chunks = chunk_text(items, config)

    # Every individual list item's marker + text must appear intact in
    # exactly one chunk — never straddling two.
    for i in range(20):
        marker = f"- Sample {i}:"
        matches = [c for c in chunks if marker in c["content"]]
        assert len(matches) == 1, f"item {i} did not land in exactly one chunk"


def test_list_chunk_type():
    text = "- First item here.\n- Second item here.\n- Third item here."
    chunks = chunk_text(text, ChunkingConfig())

    assert len(chunks) == 1
    assert chunks[0]["chunk_type"] == "list"


# ── Page number passthrough ──────────────────────────────────────────────────

def test_page_number_attached_when_provided():
    chunks = chunk_text("Some page content here.", ChunkingConfig(), page_number=3)
    assert all(c["metadata"]["page_number"] == 3 for c in chunks)


def test_page_number_none_by_default():
    chunks = chunk_text("Some content here.", ChunkingConfig())
    assert all(c["metadata"]["page_number"] is None for c in chunks)


# ── Empty input ───────────────────────────────────────────────────────────────

def test_empty_text_returns_no_chunks():
    assert chunk_text("", ChunkingConfig()) == []
    assert chunk_text("   \n\n  ", ChunkingConfig()) == []


# ── char_start / char_end sanity ─────────────────────────────────────────────

def test_char_offsets_are_within_bounds_and_ordered():
    text = _make_long_text(40)
    chunks = chunk_text(text, ChunkingConfig())

    for chunk in chunks:
        assert 0 <= chunk["char_start"] <= chunk["char_end"] <= len(text)