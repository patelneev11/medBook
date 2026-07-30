# Session 04 — File Upload Pipeline & S3 Integration

## What Was Built

- Wired the `/documents/upload` endpoint to actually validate, store, and record files end-to-end (previously a Session 3 placeholder)
- Built `services/storage.py` — a boto3-based S3 service: upload, presigned GET URLs, delete, head/size lookup
- Built `services/file_validator.py` — MIME/extension allow-list, max-size check, filename sanitization
- Added two new document endpoints: presigned `download` and `view` URLs
- Added `display_name` column to `documents` (migration `b9e1f2a3c4d5`) so users can see a friendly name distinct from the sanitized storage filename
- Built the document grid page: search, type filter, sort, pagination, status polling for in-progress documents
- Built the upload flow: drag-and-drop dropzone with per-file progress, retry, and cancel; a modal that hosts it from anywhere in the dashboard
- Built a PDF/image viewer (presigned URL in an iframe or `<img>`); non-viewable types fall through to a direct download
- Added delete with a confirm dialog and optimistic removal from the grid
- Added a toast notification system (success/error/info/warning) and wired it into upload, delete, and session-expiry events
- Added an "Upload" button to the top bar, available on every dashboard page

## S3 Configuration

| Setting | Value |
|---|---|
| Bucket | `medbook-uploads-dev` |
| Region | `us-east-2` |
| Server-side encryption | `AES256` (set on every `put_object`) |

Configured via `AWS_BUCKET_NAME` / `AWS_REGION` in `backend/.env` (see `backend/mednotebook_backend/config.py`). Not committed — `backend/.env.example` was cleared of sample values this session, so copy the variable names from the [README's env table](../README.md#environment-variables) when setting up a new machine.

## File Limits

Enforced in `file_validator.validate_file()`:

- **Max size:** 50 MB (`MAX_UPLOAD_SIZE_MB` in `.env`, default `50`) — oversized files get `413 FILE_TOO_LARGE`
- **Allowed types** (by MIME type + extension, both must match) — mismatches get `415 UNSUPPORTED_FILE_TYPE`:

  | MIME type | Extension(s) |
  |---|---|
  | `application/pdf` | `.pdf` |
  | `text/csv` | `.csv` |
  | `text/plain` | `.txt` |
  | `application/vnd.openxmlformats-officedocument.spreadsheetml.sheet` | `.xlsx` |
  | `application/vnd.ms-excel` | `.xls` |
  | `image/jpeg` | `.jpg`, `.jpeg` |
  | `image/png` | `.png` |
  | `image/tiff` | `.tiff`, `.tif` |
  | `application/json` | `.json` |
  | `text/markdown` | `.md` |

- **Filename safety:** rejects `..`, `/`, `\`, null bytes, and names over 255 chars; `sanitize_filename()` then strips the name to alphanumeric/dash/underscore and caps it at 100 chars (extension preserved)

## S3 Key Structure

Built by `storage._build_key()`:

```
uploads/{user_id}/{year}/{month:02d}/{uuid4}-{sanitized_filename}
```

Example: `uploads/00000000-0000-0000-0000-000000000001/2026/07/3f9a1c2e-...-lab_notes.pdf`

Keys are date-partitioned per user and UUID-prefixed so two uploads of the same filename never collide. Before the S3 call completes, the `Document` row holds a placeholder key (`pending/{uuid4}`) so a DB record exists even if the upload fails midway; `delete_document` skips the S3 call entirely for any row still in that `pending/` state.

## New/Updated API Endpoints

All under `/api/v1/documents`. Auth is not wired up yet — every request currently operates as a hardcoded placeholder user (`00000000-0000-0000-0000-000000000001`).

| Method | Path | Purpose |
|---|---|---|
| GET | `/documents` | List documents for the current user — filters: `project_id`, `status`, `mime_type`; paginated |
| POST | `/documents/upload` | **(newly real)** Multipart upload — validates, uploads to S3, creates the DB record, queues extraction as a background task |
| GET | `/documents/{id}` | Fetch a single document (used by the grid's status-polling loop) |
| PATCH | `/documents/{id}` | Update `project_id` and/or `status` |
| DELETE | `/documents/{id}` | Delete the S3 object (if uploaded) and the DB row |
| GET | `/documents/{id}/download` | **(new)** Presigned S3 GET URL, 1 hour expiry — triggers a browser download |
| GET | `/documents/{id}/view` | **(new)** Presigned S3 GET URL, 5 minute expiry — used by the in-app PDF/image viewer |
| GET | `/documents/{id}/chunks` | Still a placeholder — returns `[]` until Session 5 |
| POST | `/documents/{id}/summarize` | Still a placeholder — returns 202 until Session 6 |

## New Frontend Components

- [`components/upload/FileUpload.tsx`](../frontend/components/upload/FileUpload.tsx) — drag-and-drop dropzone with a per-file list (icon, size, progress bar, status, retry/cancel)
- [`components/upload/UploadModal.tsx`](../frontend/components/upload/UploadModal.tsx) — modal shell hosting `FileUpload`, reachable from the top bar on any dashboard page
- [`components/documents/DocumentViewer.tsx`](../frontend/components/documents/DocumentViewer.tsx) — full-screen PDF/image preview using the presigned `/view` URL; non-viewable types redirect straight to download
- [`components/ui/ConfirmDialog.tsx`](../frontend/components/ui/ConfirmDialog.tsx) — generic confirm/cancel dialog, used for delete
- [`components/ui/Toast.tsx`](../frontend/components/ui/Toast.tsx) — toast + container, 4-variant (success/error/info/warning), auto-dismiss after 4s, capped at 4 visible
- [`context/UploadContext.tsx`](../frontend/context/UploadContext.tsx) — open/close state for the upload modal + an `uploadedCount` signal the document grid watches to trigger a refetch
- [`context/ToastContext.tsx`](../frontend/context/ToastContext.tsx) — toast dispatch, also listens for a `mednotebook:session-expired` event fired by `lib/api.ts` on 401s
- [`hooks/useFileUpload.ts`](../frontend/hooks/useFileUpload.ts) — drives uploads via `XMLHttpRequest` (for progress events), manages per-file state, supports cancel/retry
- [`types/document.ts`](../frontend/types/document.ts) — shared `Document` type matching the backend's `DocumentResponse` schema

The document grid itself ([`app/(dashboard)/dashboard/documents/page.tsx`](../frontend/app/(dashboard)/dashboard/documents/page.tsx)) was rewritten substantially: card grid with type icons, client-side search/filter/sort, pagination, a 3-second poll for any document still `pending`/`processing`, and the view/download/delete actions.

## Testing the Upload Manually

1. Make sure `backend/.env` has real `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_BUCKET_NAME` / `AWS_REGION` values for an S3 bucket you control.
2. Sanity-check the S3 credentials/bucket directly, independent of the API:
   ```bash
   cd backend && source venv/bin/activate
   python -m mednotebook_backend.services.storage
   ```
   This uploads a small test file, verifies its size, generates a presigned URL, then deletes it — prints `All checks passed.` on success.
3. Start the backend (`uvicorn mednotebook_backend.main:app --reload --port 8001`) and frontend (`npm run dev`).
4. In the app, click **Upload** in the top bar, drag in a file (or click to browse). Watch the progress bar, then confirm the card appears in the document grid.
5. Try the edge cases: a file over 50 MB (expect a "File is too large" toast), an unsupported type like `.docx` (expect "File type not supported"), and cancelling mid-upload (item should disappear).
6. Click a PDF or image card to confirm the viewer opens with the presigned URL; click **Download** to confirm it opens the file directly.
7. Delete a document and confirm it disappears immediately and doesn't reappear on refresh; check the S3 bucket to confirm the object is gone.

## AWS Costs to Be Aware Of

- **S3 Free Tier** (first 12 months on a new AWS account): 5 GB standard storage, 20,000 GET requests/month, 2,000 PUT requests/month — this dev workflow (small files, manual testing) stays well within that.
- Beyond free tier: S3 Standard is ~$0.023/GB/month storage plus ~$0.005 per 1,000 PUT requests and ~$0.0004 per 1,000 GET requests (us-east-2 pricing, subject to change) — negligible at this scale, but worth checking the [AWS Billing dashboard](https://console.aws.amazon.com/billing/) if uploads are scripted/load-tested.
- Presigned URLs don't incur cost themselves; the GET they authorize does when the browser fetches it. The 5-minute expiry on `/view` and 1-hour on `/download` mostly bound *how long a link stays usable*, not cost.
- No lifecycle rules are configured yet — deleted documents remove their S3 object immediately via the API, but anything left in `pending/` from a failed upload (DB row created, S3 call never completed) is orphaned in Postgres, not S3, so it costs nothing.

## What's Still Not Working

- **Text extraction** — uploaded files sit in S3 with a DB row in `processing` status and never move to `ready`. `_queue_extraction()` in `routers/documents.py` only logs; it doesn't call anything yet. This is Session 5.
- `GET /documents/{id}/chunks` returns `[]` unconditionally — no chunks exist until extraction runs.
- `POST /documents/{id}/summarize` is still a 202 placeholder — no AI wiring until Session 6.
- No authentication yet — all documents are owned by a single hardcoded placeholder user ID.
- The "Move to project" and "Summarize" items in the document card's dropdown menu are present in the UI but not wired to any action.
- The project selector in the upload modal is hidden (`MOCK_PROJECTS` is empty) since there's no real projects API call wired in yet.

## Session 5 Plan: Document Parsing & Text Chunking

- Replace `_queue_extraction()` with a real background job that pulls the file back from S3 and extracts text (PDF via a text-extraction library, CSV/text files read directly, images likely deferred or OCR'd)
- Chunk extracted text into overlapping segments sized for embedding, store rows in the `chunks` table (already modeled with a pgvector column)
- Flip `Document.status` from `processing` → `ready` (or `error`) once extraction finishes, and populate `page_count` / `word_count`
- Implement `GET /documents/{id}/chunks` for real
- Surface extraction errors in the UI (the grid's polling loop already handles a `ready`/`error` status, so this is mostly backend work)

---

## Related Session Notes

- [Session 03](session-03-notes.md) — Backend structure, database models, API scaffold (documents endpoints originally stubbed here)