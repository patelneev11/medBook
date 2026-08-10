# Session 05 — Document Parsing & Chunking Pipeline

## 1. The Pipeline, in Plain English

Uploading a file and having it become "ready" involves two separate processes:
the FastAPI backend (fast, synchronous, handles the HTTP request) and a Celery
worker (slow, asynchronous, does the actual parsing in the background).

**In the request/response cycle** (`POST /api/v1/documents/upload`):

1. The backend validates the file (size, mime type, filename), sanitizes the
   filename, and creates a `documents` row with `status="pending"`.
2. It uploads the raw bytes to S3.
3. It flips the row to `status="processing"` and hands the document ID to
   Celery (`process_document.delay(id)`) — this just publishes a message to
   Redis and returns immediately. The HTTP response comes back in well under
   a second regardless of how big the file is.

**In the background** (a Celery worker process, picking the job up off Redis
whenever it's free):

1. **Load** — fetch the document row, mark `processing_started_at`.
2. **Download** — pull the raw bytes back out of S3 using the stored
   `file_key`.
3. **Parse** — look up the right parser for the file's mime type
   (`get_parser`), run it. Every parser returns the same shape: full text,
   a per-page/per-sheet breakdown, `page_count`, `word_count`, and which
   extraction method it used.
4. **Chunk** — run each page's text through the chunker (see §3), producing
   an ordered list of chunks, each tagged with its type, token count, and
   originating page number.
5. **Store** — delete any chunks left over from a previous attempt (so
   retries don't duplicate), then batch-insert the new ones into
   `document_chunks` (100 rows at a time). The `embedding` column is left
   `NULL` — that's Session 6's job.
6. **Finish** — flip the document to `status="ready"`, set
   `processing_completed_at`, `chunk_count`, `word_count`, `page_count`,
   `extraction_method`.
7. **Audit** — write a `document.processed` row to `audit_logs` with word
   count, chunk count, page count, and extraction method in its metadata.

If anything fails, which step it fails at determines what happens next — see
§8 and the retry behavior isn't guesswork, it's three distinct paths:
document-not-found (log and stop, nothing to retry), a parse failure (mark
`error` immediately, no retry — a corrupt file won't fix itself), or anything
else including a download failure (mark `error`, retry with backoff up to 3
times, `60s * (attempt number)` between tries).

The frontend polls `GET /documents/{id}/status` every 3 seconds while a
document is `pending`/`processing`, updates the card in place, and fires a
toast the moment it lands on `ready` or `error`.

## 2. Supported File Types & Parsers

All parsers live in `backend/mednotebook_backend/services/parsers/` and are
looked up by mime type via `get_parser()` in that package's `__init__.py`.

| Mime type | Extension | Parser | Library |
|---|---|---|---|
| `application/pdf` | `.pdf` | `pdf_parser.py` | pdfplumber, falling back to Tesseract OCR (via pdf2image) for scanned pages |
| `text/csv` | `.csv` | `csv_parser.py` | pandas |
| `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `.xlsx` | `csv_parser.py` | openpyxl |
| `application/vnd.ms-excel` | `.xls` | `csv_parser.py` | openpyxl — **doesn't actually work**, see §8 |
| `text/plain` | `.txt` | `text_parser.py` | — |
| `text/markdown` | `.md` | `text_parser.py` | regex-based markdown stripper |
| `application/json` | `.json` | `text_parser.py` | stdlib `json` |
| `image/jpeg`, `image/png`, `image/tiff` | `.jpg/.jpeg`, `.png`, `.tiff/.tif` | `image_parser.py` | Pillow + Tesseract OCR |

A few things every parser does regardless of file type, worth knowing about:

- Every parser returns the identical dict shape (`text`, `pages`,
  `page_count`, `word_count`, `is_scanned`, `extraction_method`, `metadata`)
  so the Celery task doesn't need to know which parser ran.
- PDF, CSV, and text all detect and flag likely medical content: patient ID
  columns, date columns, and lab values (`126 mg/dL` style patterns) get
  surfaced in metadata, and lab values in PDF prose get protected from being
  split across a chunk boundary (see §3).
- CSV/Excel tables get rendered as clean markdown tables in the extracted
  text, not just dumped as raw rows — the chunker treats a markdown table as
  a single unbreakable unit.

## 3. The Chunking Strategy

`backend/mednotebook_backend/services/chunker.py` — `chunk_text(text, config,
page_number=None)`.

**Why semantic chunking instead of fixed-size (e.g. "every 500 tokens")**:
fixed-size chunking doesn't know where a sentence ends, so it routinely
splits a sentence in half, separates a lab value from its unit
(`"...glucose measured 126"` / `"mg/dL was recorded..."`), or slices a table
into two useless fragments. For a system whose entire job is retrieving the
*right* chunk to answer a question, chunk quality is retrieval quality — a
half-sentence or half-table chunk is much less useful to an LLM (or to a
human reading the citation) than a complete one.

What it actually does:

1. Splits text at natural boundaries first — blank lines, markdown/ALL-CAPS
   headers, tables (detected by `|` characters), and lists — before ever
   looking at token counts.
2. A block that fits under `max_chunk_tokens` (default 512) becomes one
   chunk as-is. An oversized block gets split further: by sentence for
   prose, by list item for lists — never mid-sentence, never mid-item.
3. **Tables are never split**, full stop, even if that means a chunk goes
   over budget. A half-table is worse than an oversized chunk.
4. Consecutive chunks from splitting the *same* oversized section overlap by
   `overlap_tokens` (default 64) — the literal last N tokens of the previous
   chunk, decoded back to text via tiktoken — so context isn't lost right at
   a chunk boundary. Overlap does not carry across unrelated sections; each
   top-level section starts clean.
5. Anything under `min_chunk_tokens` (default 50) gets merged into a
   neighbor rather than existing as an orphaned tiny chunk — this is also
   what turns a lone header into a combined `"header+content"` chunk.
6. Chunking happens **per page**, not on the whole document as one blob —
   for single-page documents this is identical either way, but for a
   multi-page PDF it means every chunk carries an accurate `page_number` for
   citations, which chunking the whole joined text would lose.
7. Token counts use `tiktoken`'s `cl100k_base` encoding — the same
   tokenizer family used by the Claude/GPT model classes — so `token_count`
   reflects what the LLM will actually be billed/limited on, not just a word
   count approximation.

## 4. Starting the Celery Worker

```bash
cd backend
source venv/bin/activate
python -m celery -A worker.celery_app worker --loglevel=info --pool=threads --concurrency=4
```

Two details that matter and will bite you if skipped:

- **Use `python -m celery`, not the bare `celery` command.** The `celery`
  console-script entry point doesn't add the current directory to
  `sys.path`, so it can't find the `tasks` package. `python -m celery` does.
- **`--pool=threads` is required on macOS**, not optional. Celery's default
  prefork pool forks worker processes, and on macOS that reliably segfaults
  the first time a forked child makes a network call (`getaddrinfo` isn't
  fork-safe here) — confirmed via a native crash trace during this session,
  not a guess. Threads avoid forking entirely, and since the two things that
  actually dominate this workload's time (the S3 download and Tesseract OCR,
  a subprocess call) both release Python's GIL, threads still give real
  parallelism for this specific workload. On Linux, prefork would likely be
  fine, but there's no reason to switch back — threads work correctly on
  both.

Redis must be running first (`redis-cli ping` should return `PONG`) — it's
both the task queue and the result backend.

## 5. Monitoring Background Jobs

The worker logs one line per pipeline step, so a healthy run in the terminal
looks like this:

```
[...] Task tasks.document_tasks.process_document[<task-id>] received
[...] Processing started for labs.csv (text/csv)
[...] Extracted 288 words from labs.csv
[...] Created 2 chunks from labs.csv
[...] Processing complete for labs.csv — 2 chunks ready for embedding
[...] Task tasks.document_tasks.process_document[<task-id>] succeeded in 0.13s: None
```

What the failure paths look like, so you can tell them apart at a glance:

- **Permanent failure** (corrupt file — won't retry):
  `Permanent failure processing document <id>: Failed to extract text: ...`
  followed immediately by `succeeded in ...s: None` — that "succeeded" is
  Celery's own bookkeeping (the *task function* returned normally, since it
  caught the error itself), not a claim that processing worked.
- **Retryable failure** (e.g. S3 unreachable):
  `Processing failed for document <id> (attempt 1/4): Failed to download
  file from storage` followed by `retry: Retry in 60s: RuntimeError(...)`.
  The countdown doubles each attempt (60s, 120s, 180s) up to `max_retries=3`,
  after which it logs a final permanent-failure line and stops.
- A one-off `UserWarning` from pandas about date format inference on CSV
  parsing is benign noise, not an error — it doesn't affect the output.

`task_track_started=True` and `task_acks_late=True` are set in `worker.py`
so a task only leaves the queue once it's actually finished — if the worker
process dies mid-task, Redis still has the job and another worker will pick
it up.

## 6. The `document_chunks` Table

| Column | Type | Notes |
|---|---|---|
| `id` | UUID, PK | |
| `document_id` | UUID, FK → `documents.id` | `ON DELETE CASCADE` — deleting a document deletes its chunks |
| `chunk_index` | integer | 0-based, sequential across the whole document (not just within a page) |
| `content` | text | the chunk's actual text |
| `chunk_type` | enum: `paragraph` / `table` / `list` / `header+content` | nullable |
| `embedding` | `vector(1536)` (pgvector) | **NULL until Session 6** |
| `page_number` | integer | nullable — null for file types without a page concept |
| `token_count` | integer | via `tiktoken` `cl100k_base` |
| `created_at` | timestamptz | |

## 7. "ready" vs. the Future "indexed" Status

`status="ready"` means steps 1–7 of the pipeline (§1) finished successfully:
text is extracted, chunked, and every chunk is sitting in `document_chunks`
with real `content` and `token_count`. It does **not** mean the document is
searchable yet — `embedding` is `NULL` on every chunk, so there's no vector
for a similarity search to match against. A document can be fully "ready"
and still be invisible to the Ask AI feature.

Session 6 adds a second status, `indexed`, for once embeddings actually
exist for every chunk. Concretely: `ready` = "the text exists and is
chunked", `indexed` = "the text exists, is chunked, *and* is searchable."

## 8. Known Limitations

- **Scanned PDF / image OCR quality depends entirely on image quality.**
  Low resolution, poor contrast, or skewed scans produce genuinely bad OCR
  output — the pipeline does upscale small images and applies mild
  sharpening, and flags a `warning` in metadata when Tesseract's own
  confidence drops below 60%, but it can't fix a bad source image.
- **Legacy binary `.xls` files don't actually parse.** `openpyxl` (what the
  Excel parser is built on) only reads the OOXML `.xlsx` format. A real
  old-format `.xls` upload fails with a clear error ("not a zip file"), not
  a silent misparse — but it does fail. Real `.xls` support would need the
  `xlrd` package added as a dependency.
- **Complex Excel layouts aren't guaranteed to parse cleanly.** The parser
  handles the common cases explicitly — a title banner merged across a full
  row gets pulled out as a caption, a value merged down several rows gets
  filled into each row — but deeply nested headers, multiple banner rows in
  a row, or pivoted/cross-tab layouts weren't specifically designed for and
  may produce a confusing table.
- **PDF header/footer stripping only catches byte-identical repeats.** A
  footer that includes a page number (`"Page 3 of 12"`) is different on
  every page, so it won't be recognized as a repeated footer and will stay
  in the extracted text.
- **Table detection is pattern-based (`|` characters), not layout-based.**
  A table that's already been OCR'd from a scanned PDF or image is just
  plain text by the time the chunker sees it — there's no way to know it
  was originally tabular, so it gets chunked as prose.
- **Sentence splitting is a simple regex** (period/question/exclamation +
  space + capital letter), not real NLP. It handles decimals correctly
  (`7.2` never triggers it) but can occasionally misfire on abbreviations
  like `"Dr. Smith"` or non-English text.
- **OCR is English-only right now** — `lang="eng"` is hardcoded in the image
  and PDF-OCR-fallback parsers.

## 9. What Session 6 Will Build

Embeddings and vector search — the piece that makes `ready` documents
actually queryable:

- Generate an embedding per chunk (via Claude's embedding API or a
  dedicated embedding model) and store it in the `document_chunks.embedding`
  column that's sitting empty right now.
- Add the `indexed` status described in §7, set once every chunk for a
  document has a real embedding.
- Build the actual similarity search — given a question, embed it and find
  the nearest chunks via pgvector.
- Wire up the Ask AI page for real: it currently has `HAS_DOCUMENTS = false`
  hardcoded and a disabled send button; this is where that becomes live.

---

## Related Session Notes

- [Session 04](session-04-notes.md) — File upload pipeline (S3, upload/download/view endpoints, document grid)
