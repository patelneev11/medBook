# Session 06 — Embeddings & Semantic Search

> **Note on the embedding model:** the original Session 6 plan called for
> Claude's hosted embedding API (`text-embedding-3-small`, 1536 dimensions).
> Partway through the session that decision was revisited and switched to a
> **local** `sentence-transformers` model instead — see §2 for why. Every
> number in this document (dimensions, cost, latency) reflects what's
> actually running, not the original plan.

## 1. The Embedding Pipeline, in Plain English

Session 5 leaves a document in `status="ready"` with every chunk stored in
`document_chunks`, but `embedding` is `NULL` on all of them — nothing is
searchable yet. Session 6 adds the second half of the pipeline that closes
that gap.

The moment Session 5's parsing task finishes and flips a document to
`ready`, it immediately hands off to a second, independent Celery task,
`generate_embeddings`, instead of trying to do everything in one task:

1. **Load & validate** — fetch the document, confirm `status == "ready"`
   and it actually has chunks. Set `embedding_status = "generating"`.
2. **Fetch chunks needing embeddings** — pulled in batches of 50, ordered by
   `chunk_index`, via `ChunkRepository.get_chunks_without_embeddings()`,
   which only ever selects rows where `embedding IS NULL`. This one detail
   is what makes the whole step **resumable**: if the task crashes or gets
   retried halfway through a 400-chunk document, it picks up exactly where
   it left off instead of re-embedding (and re-paying for, on a hosted
   model) chunks that already succeeded.
3. **Embed each batch** — the batch's chunk text goes through
   `generate_embeddings_batch()`, which normalizes the text (Unicode
   normalization, strips embedded nulls), truncates anything absurdly long,
   and calls the embedding model once per batch rather than once per chunk.
   If a whole batch call fails, it falls back to embedding that batch's
   chunks one at a time, so a single bad chunk doesn't blank out 49 good
   ones.
4. **Save & log progress** — each vector is written back to
   `document_chunks.embedding` along with `embedding_model` and
   `embedding_generated_at`, and the worker logs
   `Embedded {n}/{total} chunks for {filename}` after every batch.
5. **Finalize** — once every chunk has a vector, the document flips to
   `status="indexed"`, `embedding_status="complete"`, and an
   `document.indexed` row is written to `audit_logs` with the chunk count,
   token count, and estimated cost. This is also the point where a row gets
   written to `embedding_costs` (see §6).

If the task fails outright (not a single-chunk failure — the batch-level
fallback in step 3 already handles that), it retries up to 3 times with
backoff, same pattern as the parsing task. If it still fails after retries,
`embedding_status` is set to `"error"` — but note `status` stays `"ready"`,
not `"error"`: the document's text and chunks are real and still fully
viewable, it's just not searchable until the embedding step is retried.
There's a retry endpoint for exactly this case.

## 2. The Embedding Model: Local MiniLM, Not a Hosted API

**`all-MiniLM-L6-v2`, 384 dimensions, run locally via `sentence-transformers`**
(`backend/mednotebook_backend/services/embeddings.py`). Loaded once per
process (`@lru_cache`) and cached — the actual embed call is a few
milliseconds once warm.

Why not the originally-planned hosted `text-embedding-3-small` (1536-dim)
API:

- **Zero marginal cost.** Every chunk of every document gets embedded, and
  re-embedded on any reprocess — with a hosted API that's a real, ongoing
  bill; local inference is free per call.
- **No external dependency in the hot path.** Document indexing doesn't
  break because a third-party API had an outage or rate-limited us.
- **Data stays on our infrastructure.** These are medical research
  documents — not sending chunk text to an external embeddings endpoint at
  all is a meaningfully simpler privacy story than "sent, but not stored"
  by a vendor.

The tradeoff: MiniLM is a smaller, weaker model than a large hosted
embedding model, and it has its own hard internal limit — it silently
truncates at 256 tokens regardless of how much text you feed it (see §9).
The `document_chunks.embedding` column was migrated from `vector(1536)`
down to `vector(384)` to match.

Because there's no real per-call API cost with this model, the
`embedding_costs` table (§6) tracks a **notional** cost using a
configurable hosted-API-equivalent rate — useful for "what would this have
cost on a typical hosted embeddings API," not a real bill.

## 3. How pgvector Similarity Search Works

Every chunk's `embedding` column is a pgvector `vector(384)`. A search
query gets embedded with the exact same model, and then the database finds
the chunks whose vectors are closest to it:

```python
distance = DocumentChunk.embedding.cosine_distance(query_vector)
similarity = 1 - distance
```

`cosine_distance()` compiles to pgvector's `<=>` operator. Both the stored
chunk vectors and the query vector are unit-normalized
(`normalize_embeddings=True` at embed time), so cosine distance and a plain
dot product are mathematically equivalent here — `1 - distance` gives a
similarity score in roughly `[0, 1]`, where 1.0 is an identical vector.

Results are filtered to `similarity > 0.35` (the default relevance floor)
and ordered by distance ascending (closest first), then limited.

**The index**: `idx_chunks_embedding_ivfflat`, an IVFFLAT index with
`lists=100` on `vector_cosine_ops`. IVFFLAT is *approximate* nearest-neighbor
search — it clusters vectors into `lists` buckets at index-build time and
only searches the buckets nearest the query, trading a small amount of
recall for a lot of speed. `lists=100` is a reasonable starting point for a
small/dev-sized corpus; as the corpus grows substantially, the index
benefits from a `REINDEX` to re-cluster (a stale IVFFLAT index on a much
larger table than it was built for degrades gracefully in speed, not
correctness — it just gets less accurate at finding the true nearest
neighbors).

## 4. Three Search Modes, and When to Use Each

All three live in `backend/mednotebook_backend/services/search.py` and are
selectable per-request via `search_type` on `POST /api/v1/search`.

| Mode | How it works | Best for |
|---|---|---|
| **Semantic** | Embeds the query, finds chunks by cosine similarity (§3) | Natural-language questions, conceptual queries where the exact wording won't appear in the text ("what causes insulin resistance" matching a passage that never uses those exact words) |
| **Keyword** | PostgreSQL full-text search (`websearch_to_tsquery` + `ts_rank_cd` over a generated `tsvector` column) | Exact terms, acronyms, drug names, lab codes, or anything where matching the literal words matters more than the concept |
| **Hybrid** (default) | Runs both, fuses the two ranked lists via Reciprocal Rank Fusion (`1/(60+rank)` per list, summed) | General-purpose default — recovers from either mode's blind spot |

One concrete thing worth knowing: `websearch_to_tsquery` treats
space-separated terms as an **AND**, not an OR. A query like `"HOMA-IR
fasting insulin threshold 2.5"` typed as a natural sentence can return
**zero** keyword results even when every individual word appears in the
document, because no single chunk contains all five terms together. This
is exactly the case hybrid mode exists for — semantic search doesn't care
about exact co-occurrence, so hybrid still surfaces the right chunks by
fusing in the semantic list.

## 5. Document Status Flow

```
pending → processing → ready → indexed
                ↓                  ↓
              error            (embedding_status="error";
                                 status stays "ready")
```

| `status` | Meaning |
|---|---|
| `pending` | Uploaded, not yet picked up by a worker |
| `processing` | Parsing/chunking in progress |
| `ready` | Text extracted and chunked — fully viewable, **not yet searchable** |
| `indexed` | Every chunk has a real embedding — searchable |
| `error` | Parsing itself failed (corrupt file, unsupported content) |

`embedding_status` (`pending` / `generating` / `complete` / `error`) tracks
the embedding step specifically, independent of `status` — this is what
lets a document be permanently stuck on "embedding failed" while still
being fully readable, rather than lumping that failure into the same
`error` state as a genuinely unparseable file.

## 6. Estimating Embedding Costs

Two different things answer two different questions:

- **"What would embedding this text cost?"** — `estimate_embedding_cost()`
  in `services/embeddings.py`. Counts tokens with `tiktoken`'s `cl100k_base`
  encoding (a reasonable proxy tokenizer, not MiniLM's own) and returns
  `{total_tokens, chunk_count, estimated_cost_usd}`. Since MiniLM runs
  locally, `estimated_cost_usd` is always `0.0` here — this function
  answers "how many tokens," not "how many dollars."
- **"What did this actually cost, tracked over time?"** — the
  `embedding_costs` table, written once per document at the moment it
  finishes indexing. Unlike the function above, this uses a configurable
  notional rate (`embedding_cost_per_1k_tokens_usd`, currently `$0.00002`
  per 1k tokens — a typical hosted-API-equivalent price) purely for
  monitoring: "if we were paying for this, what would the bill look like."
  `GET /api/v1/admin/embedding-costs` aggregates this into total cost this
  month, top 10 users by spend, average cost per document, and a
  straight-line projected monthly cost from the current daily rate.

To estimate a **document set** ahead of time: sum `estimate_embedding_cost()`
across the planned chunk text, or — more simply — chunk count × ~250 tokens
(a rough average chunk size given `min_chunk_tokens=50` /
`max_chunk_tokens=512`) × the rate above.

## 7. The `search_logs` Table

Every `POST /api/v1/search` request writes a row here, separate from the
user-facing `search_history` table (which stores the plain query text for
a "recent searches" list). `search_logs` is for aggregate monitoring, not
display, so it never stores the raw query:

| Column | Captures |
|---|---|
| `query_hash` | SHA-256 of the query text — never plain text |
| `search_type` | `semantic` / `keyword` / `hybrid` |
| `result_count` | How many results came back |
| `search_time_ms` | Server-side search duration |
| `had_results` | Boolean — did anything come back at all |
| `user_id`, `project_id` | Who searched, and scoped to which project (if any) |
| `created_at` | When |

This is what makes three kinds of analysis possible over time: which
queries return nothing (content gaps — maybe the corpus is missing that
topic, or chunking is splitting it badly), whether semantic or hybrid mode
tends to perform better for this corpus, and whether search latency is
drifting. On that last point: after every search, a rolling average over
the last 20 `search_logs` rows is checked, and a `warning` (>2s average) or
`error` (>5s average) is logged if it's climbing — a *sustained* trend, not
a single slow request, since one outlier shouldn't page anyone.

## 8. Search Latency Observed During Testing

Measured against a small test corpus (2 documents, 6 chunks total) — real
numbers, not estimates:

- **Server-reported `search_time_ms`** (from the API response itself):
  1–10ms for keyword, 8–30ms for semantic/hybrid once the embedding model
  is warm. A one-time ~200–450ms spike appears on the very first request
  after a process (re)start — that's the `@lru_cache`-wrapped MiniLM model
  loading from disk, not a query cost, and it only happens once per process
  lifetime.
- **Full browser round-trip** (measured via Chrome DevTools Protocol
  network timestamps, not just server time): 15–30ms warm, ~200ms on the
  first request of a session.

All of the above is comfortably under the 500ms target with real headroom.
Caveat worth being honest about: this is a 6-chunk corpus. The IVFFLAT
index's approximate-search behavior, and its `lists=100` tuning, aren't
meaningfully exercised at this scale — both search quality and latency
behavior at, say, 100k+ chunks are unverified and may need retuning
(`lists` should scale roughly with `sqrt(row count)`, and a `REINDEX` will
matter once the corpus is actually large).

## 9. Known Limitations

- **Retrieval quality is capped by parse quality.** A search can only find
  what got extracted — OCR errors on a scanned PDF, a garbled table, or a
  parser artifact all become part of what gets embedded and searched. This
  pipeline can't distinguish "the document doesn't discuss X" from "the
  parser mangled the part that discusses X."
- **MiniLM truncates at 256 tokens internally, independent of chunk size.**
  The chunker allows chunks up to 512 tokens (`max_chunk_tokens`), but the
  embedding model silently truncates anything longer at 256 — meaning the
  back half of a large chunk can be invisible to search even though its
  full text is stored and shown to the user. This is a real, non-obvious
  gap between what's stored and what's actually searchable.
- **Very short chunks embed poorly.** A chunk near the `min_chunk_tokens=50`
  floor carries little semantic content on its own — its embedding ends up
  closer to "generic short text" than to any specific concept, which both
  weakens its own retrievability and can pollute results with a spuriously
  high similarity score for unrelated queries.
- **Keyword search is AND-only for multi-term queries** (§4) — a natural-
  language query typed into keyword-only mode can return nothing even when
  every word appears in the corpus, just not in the same chunk.
- **A permanently-failed individual chunk embeds as a zero vector**, not a
  retry-forever loop (`generate_embeddings_batch`'s per-chunk fallback).
  A zero vector is semantically meaningless — it won't match real queries,
  but it also won't surface as obviously broken; there's no automated
  detection of these chunks today.
- **IVFFLAT recall is approximate and untested at scale** — see the caveat
  in §8.
- **Single-user placeholder auth throughout** — every table has real
  `user_id`/`project_id` columns and the query/index logic is already
  written to scope by them, but there's exactly one user in practice today,
  so multi-tenant isolation is unverified under real concurrent load.

## 10. What Session 7 Will Build

This is where the product stops being "a search engine over your documents"
and becomes "a research assistant that answers questions with sources" —
the actual point of MedNotebook.

- Wire the Ask AI page (currently gated on "at least one document indexed,"
  §5) to a real pipeline: take the user's question, run it through hybrid
  search (§4) to retrieve the relevant chunks, then send those chunks plus
  the question to the Claude API as context.
- Return an answer that cites its sources — linking back to the specific
  document, page, and chunk each part of the answer came from, not just a
  wall of generated text.
- Persist real `AIQuery` rows (`question`, `answer`, `sources`,
  `tokens_used`, `response_time_ms`) — `create_query` today is still a
  Session 6-era stub that doesn't write to the database.
- Some of this session's work already anticipates it: `AIQuery` has
  `search_log_id` (links an answer back to the exact search request that
  fed it) and a nullable `helpful` rating column, plus a working
  `PATCH /queries/{id}/feedback` endpoint — currently 404s on everything
  since no real query rows exist yet, but the data model and endpoint are
  ready for Session 7 to populate for real.

---

## Related Session Notes

- [Session 05](session-05-notes.md) — Document parsing & chunking pipeline (the "ready" status this session builds on top of)