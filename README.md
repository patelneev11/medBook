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
| JWT Authentication | 🔲 Session 4 |
| File upload + S3 | 🔲 Session 5 |
| AI / RAG pipeline | 🔲 Session 6 |

---

## Getting Started

### 1. Start the database

```bash
# From the project root
docker compose up -d
```

This starts PostgreSQL 16 with pgvector on **port 5433**.

### 2. Backend (FastAPI)

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

### 3. Frontend (Next.js)

```bash
cd frontend
npm install
npm run dev
```

- URL: `http://localhost:3001` (port 3000 is occupied on this machine)

---

## Backend Structure

```
backend/mednotebook_backend/
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
│   ├── documents.py
│   └── queries.py
├── schemas/           # Pydantic v2 request/response models
│   ├── common.py      # HealthResponse, PaginatedResponse[T], ErrorResponse
│   ├── user.py
│   ├── project.py
│   ├── document.py
│   └── query.py
└── services/          # Business logic stubs (wired in Sessions 5–6)
    ├── storage.py     # S3 upload/download
    ├── embeddings.py  # Claude embedding generation
    └── ai.py          # RAG pipeline
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
| `AWS_ACCESS_KEY_ID` | Session 5 | S3 file uploads |
| `AWS_SECRET_ACCESS_KEY` | Session 5 | S3 file uploads |
| `AWS_BUCKET_NAME` | Session 5 | Create an S3 bucket first |
| `AWS_REGION` | Session 5 | `us-east-1` |
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
| Documents | 7 | `/documents` |
| Queries | 3 | `/queries` |

See [Session 03 notes](docs/session-03-notes.md) for the full endpoint list.

---

## Session Notes

- [Session 01](docs/session-01-notes.md) — Project scaffold, frontend + backend bootstrapped
- [Session 02](docs/session-02-notes.md) — Frontend skeleton, design system, dark mode, all pages
- [Session 03](docs/session-03-notes.md) — Backend structure, database models, API scaffold, frontend/backend connected
