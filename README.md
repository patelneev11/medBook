# MedNotebook

A secure AI-powered document workspace for medical researchers and biology students.

## What it does

Users upload documents (PDFs, CSVs, images, text files). The app extracts the text, stores it with vector embeddings, and lets users ask AI-powered questions about their documents — with answers that include source citations.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 16 (React 19) with TypeScript and Tailwind CSS v4 |
| Backend | Python 3.12 + FastAPI (async) |
| Database | PostgreSQL 16 + pgvector |
| File Storage | AWS S3 |
| AI | Claude API (Anthropic) |
| ORM | SQLAlchemy 2.0 (async) + Alembic |

## Project Structure

```
medBook/
├── frontend/          # Next.js web app
├── backend/           # FastAPI Python server
├── docs/              # Session notes and project documentation
├── docker-compose.yml # PostgreSQL + pgvector container
├── README.md
└── .gitignore
```

## Current Status

| Area | Status |
|------|--------|
| Frontend skeleton | ✅ Complete (Session 2) |
| Design system + dark mode | ✅ Complete (Session 2) |
| Backend package structure | ✅ Complete (Session 3) |
| Database models (7 tables) | ✅ Complete (Session 3) |
| Pydantic schemas + validation | ✅ Complete (Session 3) |
| API endpoints (27 routes) | ✅ Routed — placeholder responses (Session 3) |
| Request logging + error handlers | ✅ Complete (Session 3) |
| Frontend → Backend connection | ✅ Complete (Session 3) |
| File upload + S3 | ✅ Complete (Session 4) |
| JWT Authentication | 🔲 Not started |
| Text extraction + chunking | ✅ Complete (Session 5) |
| Background job processing (Celery + Redis) | ✅ Complete (Session 5) |
| Embeddings + semantic/keyword/hybrid search | ✅ Complete (Session 6) — documents show **"Indexed"** once fully searchable |
| AI Q&A with citations (Claude API) | 🔲 Session 7 |

---

## Getting Started

MedNotebook needs **four** things running at once: Postgres, Redis, the
FastAPI backend, and the Celery worker (plus the frontend to actually use
it). Each of the following runs in its own terminal tab.

### 1. Start the database

```bash
# From the project root
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on **port 5433**.

### 2. Start Redis

Redis is the task queue between the backend and the Celery worker — it must
be running before you start either. On macOS via Homebrew:

```bash
brew services start redis
redis-cli ping   # should print PONG
```

### 3. Backend (FastAPI)

```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt

# Run migrations (first time or after model changes)
alembic upgrade head

# Start the dev server
uvicorn mednotebook_backend.main:app --reload --port 8001
```

- API base URL: `http://localhost:8001/api/v1`
- Interactive docs (Swagger): `http://localhost:8001/docs`
- Alternative docs (ReDoc): `http://localhost:8001/redoc`

### 4. Celery worker (background document processing)

This is what actually parses and chunks uploaded documents — without it,
uploads will sit in "Waiting to process" forever. Same virtualenv as the
backend, separate terminal tab:

```bash
cd backend
source venv/bin/activate
python -m celery -A worker.celery_app worker --loglevel=info --pool=threads --concurrency=4
```

Use `python -m celery`, not the bare `celery` command — the console script
doesn't add the project directory to `sys.path`, so it can't find the task
module. `--pool=threads` is required on macOS: Celery's default prefork pool
forks worker processes, and forking reliably segfaults here the first time
a forked child touches the network (an S3 call, an OCR subprocess). Threads
sidestep the fork entirely and still parallelize fine for this workload.
See [Session 05 notes](docs/session-05-notes.md) for the full pipeline this
worker runs.

### 5. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

- URL: `http://localhost:3000`

---

## Backend Structure

```
backend/
├── worker.py                    # Celery app: broker/backend config, task imports
├── tasks/
│   └── document_tasks.py        # process_document — the real parse→chunk→store pipeline
├── tests/
│   └── test_chunker.py          # Chunker unit tests (17 tests)
└── mednotebook_backend/
    ├── config.py          # Settings via pydantic-settings (reads .env)
    ├── database.py        # Async engine, session factory, Base
    ├── exceptions.py      # AppException for structured error responses
    ├── main.py            # App factory, middleware, error handlers, routers
    ├── middleware/
    │   ├── cors.py
    │   └── logging.py     # Per-request UUID, structured logging, X-Request-ID
    ├── models/            # SQLAlchemy 2.0 ORM models (7 tables)
    │   ├── user.py
    │   ├── project.py     # Project + ProjectMembership
    │   ├── document.py
    │   ├── chunk.py       # DocumentChunk with pgvector embedding
    │   ├── query.py       # AIQuery
    │   └── audit.py       # AuditLog
    ├── routers/           # FastAPI routers — all mounted under /api/v1
    │   ├── health.py
    │   ├── users.py       # /auth + /users
    │   ├── projects.py
    │   ├── documents.py   # 11 endpoints incl. status polling + retry
    │   └── queries.py
    ├── schemas/           # Pydantic v2 request/response models
    │   ├── common.py      # HealthResponse, PaginatedResponse[T], ErrorResponse
    │   ├── user.py
    │   ├── project.py
    │   ├── document.py
    │   └── query.py
    └── services/
        ├── storage.py         # S3 upload/download
        ├── file_validator.py  # Type/size validation, filename sanitization
        ├── chunker.py          # Semantic chunking engine (Session 5)
        ├── parsers/             # Per-file-type text extraction (Session 5)
        │   ├── pdf_parser.py     # pdfplumber + Tesseract OCR fallback
        │   ├── csv_parser.py     # pandas (CSV) + openpyxl (Excel)
        │   ├── text_parser.py    # txt / markdown / json
        │   ├── image_parser.py   # Pillow + Tesseract OCR
        │   └── exceptions.py     # ParserException
        ├── embeddings.py  # Claude embedding generation — Session 6
        └── ai.py          # RAG pipeline — Session 6
```

## Environment Variables

### Frontend (`frontend/.env.local`)

```
NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1
NEXT_PUBLIC_ENVIRONMENT=development
```

### Backend (`backend/.env`)

Copy `backend/.env.example` to `backend/.env` and fill in real values:

| Variable | Required now | Notes |
|----------|-------------|-------|
| `DATABASE_URL` | ✅ | `postgresql+asyncpg://mednotebook_user:mednotebook_pass@localhost:5433/mednotebook_dev` |
| `SECRET_KEY` | ✅ | Min 32 chars — generate with `python -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | ✅ | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ | `60` |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ | `30` |
| `AWS_ACCESS_KEY_ID` | ✅ | S3 file uploads |
| `AWS_SECRET_ACCESS_KEY` | ✅ | S3 file uploads |
| `AWS_BUCKET_NAME` | ✅ | S3 bucket for uploaded files |
| `AWS_REGION` | ✅ | e.g. `us-east-1` |
| `REDIS_URL` | ✅ | `redis://localhost:6379/0` — Celery broker + result backend |
| `ANTHROPIC_API_KEY` | Session 6 | Claude API for AI queries |
| `ENVIRONMENT` | ✅ | `development` |
| `ALLOWED_ORIGINS` | ✅ | `http://localhost:3000,http://localhost:3001` |

---

## API Overview

All routes are prefixed with `/api/v1`.

| Router | Endpoints | Path prefix |
|--------|-----------|-------------|
| Health | 2 | `/health` |
| Auth | 4 | `/auth` |
| Users | 3 | `/users` |
| Projects | 8 | `/projects` |
| Documents | 11 | `/documents` |
| Queries | 3 | `/queries` |

See [Session 03 notes](docs/session-03-notes.md) for the original endpoint scaffold, [Session 04 notes](docs/session-04-notes.md) for the upload/download/view endpoints added since, and [Session 05 notes](docs/session-05-notes.md) for the status-polling and retry endpoints.

---

## Session Notes

- [Session 01](docs/session-01-notes.md) — Project scaffold, frontend + backend bootstrapped
- [Session 02](docs/session-02-notes.md) — Frontend skeleton, design system, dark mode, all pages
- [Session 03](docs/session-03-notes.md) — Backend structure, database models, API scaffold, frontend/backend connected
- [Session 04](docs/session-04-notes.md) — File upload pipeline: S3 storage, upload/download/view endpoints, document grid, viewer, delete
- [Session 05](docs/session-05-notes.md) — Document parsing & chunking pipeline: Celery/Redis background jobs, PDF/CSV/Excel/text/image parsers, semantic chunker, retry support
- [Session 06](docs/session-06-notes.md) — Embeddings & semantic search: local MiniLM embedding pipeline, pgvector similarity search, semantic/keyword/hybrid search modes, "Indexed" document status, cost + search performance monitoring
