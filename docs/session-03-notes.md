# Session 03 — Backend Structure, Database Models & API Scaffold

## What Was Built

- Restructured the backend from a single `main.py` into a proper Python package (`mednotebook_backend/`)
- Defined all 7 SQLAlchemy database models with full relationships
- Set up async database connection with asyncpg + SQLAlchemy 2.0
- Configured Alembic and ran the initial schema migration against a local PostgreSQL + pgvector container
- Wrote all Pydantic v2 schemas with field validation (password strength, file size, name length)
- Built all 27 API endpoints across 5 routers — request routing is fully wired, responses are placeholder data
- Added production-quality middleware: request logging with unique request IDs, CORS
- Added global error handlers: 404, 422 (clean field-level errors), 500 (no raw exception leakage), custom `AppException`
- Connected the Next.js frontend to the backend: `lib/api.ts` typed fetch client, API status dot in the top bar

---

## Backend Folder Structure

```
backend/
├── .env                          # Real secrets — never committed to git
├── .env.example                  # Template with comments — committed to git
├── alembic.ini                   # Alembic configuration
├── alembic/
│   ├── env.py                    # Async migration runner (uses asyncpg)
│   ├── script.py.mako
│   └── versions/
│       └── 6fc55fc84e13_initial_schema.py   # Migration #1: all 7 tables
├── main.py                       # Entry point (imports mednotebook_backend.main:app)
├── requirements.txt
└── mednotebook_backend/
    ├── __init__.py
    ├── config.py                 # pydantic-settings: reads .env, exposes Settings singleton
    ├── database.py               # Async engine, session factory, Base, get_db dependency
    ├── exceptions.py             # AppException — raise anywhere for structured error responses
    ├── main.py                   # FastAPI app, middleware, exception handlers, router mounts
    ├── middleware/
    │   ├── cors.py               # CORSMiddleware wired from settings.cors_origins
    │   └── logging.py            # Per-request UUID, structured log line, X-Request-ID header
    ├── models/
    │   ├── __init__.py
    │   ├── audit.py              # AuditLog
    │   ├── chunk.py              # DocumentChunk (pgvector embedding column)
    │   ├── document.py           # Document, DocumentStatus enum
    │   ├── project.py            # Project, ProjectMembership, MemberRole enum
    │   ├── query.py              # AIQuery
    │   └── user.py               # User, UserRole enum
    ├── routers/
    │   ├── __init__.py
    │   ├── documents.py          # /api/v1/documents
    │   ├── health.py             # /api/v1/health
    │   ├── projects.py           # /api/v1/projects
    │   ├── queries.py            # /api/v1/queries
    │   └── users.py              # /api/v1/auth  +  /api/v1/users
    ├── schemas/
    │   ├── __init__.py           # Exports everything
    │   ├── common.py             # HealthResponse, PaginatedResponse[T], ErrorResponse
    │   ├── document.py           # DocumentBase/Create/Update/Response, ChunkBase/Response
    │   ├── project.py            # ProjectBase/Create/Update/Response/WithCount, MemberInvite/Update/Response
    │   ├── query.py              # QueryBase/Create/Update/Response
    │   └── user.py               # UserBase/Create/Update/Response/Profile, LoginRequest, TokenResponse, …
    └── services/
        ├── __init__.py
        ├── ai.py                 # Stub — Claude API calls (Session 6)
        ├── embeddings.py         # Stub — embedding generation (Session 5)
        └── storage.py            # Stub — S3 upload/download (Session 5)
```

---

## Database Tables

All tables live in the default PostgreSQL schema. The `pgvector` extension is enabled on first migration.

### 1. `users`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | auto-generated |
| `email` | VARCHAR(255) | unique, indexed |
| `full_name` | VARCHAR(255) | |
| `hashed_password` | VARCHAR(255) | bcrypt — never returned to client |
| `is_active` | BOOLEAN | default true |
| `is_verified` | BOOLEAN | default false — email verification (future) |
| `role` | ENUM | `owner` / `admin` / `member` |
| `created_at` | TIMESTAMPTZ | server default |
| `updated_at` | TIMESTAMPTZ | auto-updated on write |
| `last_login_at` | TIMESTAMPTZ | nullable |

### 2. `projects`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `name` | VARCHAR(255) | |
| `description` | TEXT | nullable |
| `owner_id` | UUID FK→users | CASCADE delete |
| `color` | VARCHAR(20) | hex colour, default `#1B7F6E` |
| `is_archived` | BOOLEAN | soft-delete flag |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### 3. `project_memberships`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK→projects | CASCADE delete |
| `user_id` | UUID FK→users | CASCADE delete |
| `role` | ENUM | `owner` / `editor` / `viewer` |
| `joined_at` | TIMESTAMPTZ | |
| — | UNIQUE | `(project_id, user_id)` — one row per user per project |

### 4. `documents`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `project_id` | UUID FK→projects | nullable, SET NULL on project delete |
| `uploaded_by` | UUID FK→users | CASCADE delete |
| `filename` | VARCHAR(255) | original filename |
| `file_key` | VARCHAR(500) | S3 object key |
| `file_size_bytes` | INTEGER | nullable until upload completes |
| `mime_type` | VARCHAR(100) | nullable |
| `status` | ENUM | `pending` → `processing` → `ready` / `error` |
| `page_count` | INTEGER | nullable — set after extraction |
| `word_count` | INTEGER | nullable — set after extraction |
| `summary` | TEXT | nullable — set after summarisation |
| `created_at` / `updated_at` | TIMESTAMPTZ | |

### 5. `document_chunks`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `document_id` | UUID FK→documents | CASCADE delete |
| `chunk_index` | INTEGER | order within the document |
| `content` | TEXT | raw text of this chunk |
| `embedding` | VECTOR(1536) | pgvector — null until embedding job runs |
| `page_number` | INTEGER | nullable |
| `token_count` | INTEGER | nullable |
| `created_at` | TIMESTAMPTZ | |

### 6. `ai_queries`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK→users | CASCADE delete |
| `project_id` | UUID FK→projects | nullable, SET NULL on project delete |
| `question` | TEXT | |
| `answer` | TEXT | nullable — null until RAG pipeline runs |
| `sources` | JSON | nullable — list of chunk references |
| `model_used` | VARCHAR(100) | default `claude-sonnet-4-20250514` |
| `tokens_used` | INTEGER | nullable |
| `response_time_ms` | INTEGER | nullable |
| `created_at` | TIMESTAMPTZ | |

### 7. `audit_logs`
| Column | Type | Notes |
|--------|------|-------|
| `id` | UUID PK | |
| `user_id` | UUID FK→users | nullable, SET NULL on user delete |
| `action` | VARCHAR(100) | e.g. `document.upload`, `query.create` |
| `resource_type` | VARCHAR(100) | nullable |
| `resource_id` | UUID | nullable |
| `ip_address` | VARCHAR(50) | nullable |
| `user_agent` | VARCHAR(500) | nullable |
| `metadata` | JSON | nullable (Python attribute named `meta` — `metadata` is reserved by SQLAlchemy) |
| `created_at` | TIMESTAMPTZ | |

---

## API Endpoints

All endpoints are prefixed with `/api/v1`. Interactive docs at `http://localhost:8001/docs`.

### Health

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| GET | `/health` | 200 | Returns `{status, version, environment}` |
| GET | `/health/db` | 200 | Runs `SELECT 1` against the DB; returns `{status, database}` |

### Auth (`/auth`)

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| POST | `/auth/register` | 201 | Create account — body: `{email, full_name, password}` |
| POST | `/auth/login` | 200 | Sign in — body: `{email, password}` → `{access_token, refresh_token, token_type, expires_in}` |
| POST | `/auth/refresh` | 200 | Exchange refresh token → new access token |
| POST | `/auth/logout` | 200 | Invalidate session |

### Users (`/users`)

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| GET | `/users/me` | 200 | Current user profile |
| PATCH | `/users/me` | 200 | Update `full_name` or `password` |
| GET | `/users/me/usage` | 200 | `{documents_count, queries_this_month, storage_used_bytes}` |

### Projects (`/projects`)

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| GET | `/projects` | 200 | List user's projects |
| POST | `/projects` | 201 | Create project — body: `{name, description?, color?}` |
| GET | `/projects/{id}` | 200 | Project detail + `document_count` |
| PATCH | `/projects/{id}` | 200 | Update name / description / color |
| DELETE | `/projects/{id}` | 204 | Soft-delete (`is_archived = true`) |
| GET | `/projects/{id}/members` | 200 | List collaborators |
| POST | `/projects/{id}/members` | 201 | Invite by email — body: `{email, role}` |
| DELETE | `/projects/{id}/members/{user_id}` | 204 | Remove collaborator |

### Documents (`/documents`)

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| GET | `/documents` | 200 | List documents; query params: `project_id`, `doc_status`, `mime_type` |
| POST | `/documents/upload` | 201 | Multipart upload — form fields: `file` (required), `project_id` (optional) |
| GET | `/documents/{id}` | 200 | Document detail |
| PATCH | `/documents/{id}` | 200 | Reassign to a different project |
| DELETE | `/documents/{id}` | 204 | Delete document and all its chunks |
| GET | `/documents/{id}/chunks` | 200 | List text chunks for a document |
| POST | `/documents/{id}/summarize` | 202 | Queue AI summarisation job |

### Queries (`/queries`)

| Method | Path | Response | What it does |
|--------|------|----------|--------------|
| POST | `/queries` | 201 | Ask a question — body: `{question, project_id?}` |
| GET | `/queries` | 200 | Query history for current user |
| GET | `/queries/{id}` | 200 | Single query with answer and sources |

---

## Running Migrations

PostgreSQL must be running first (see Docker section below).

```bash
cd backend
source venv/bin/activate
alembic upgrade head
```

To create a new migration after changing a model:

```bash
alembic revision --autogenerate -m "describe the change"
alembic upgrade head
```

To roll back one step:

```bash
alembic downgrade -1
```

---

## Starting the Backend

```bash
cd /Users/ankurp/Documents/git/medBook/backend
source venv/bin/activate
uvicorn mednotebook_backend.main:app --reload --port 8001
```

> Port 8001 is used on this machine because 8000 is occupied by another process. Use `--port 8000` on a clean machine.

---

## Accessing the API Docs

With the backend running, open:

- **Swagger UI** — `http://localhost:8001/docs` — interactive: try every endpoint in the browser
- **ReDoc** — `http://localhost:8001/redoc` — cleaner read-only reference

---

## Docker (PostgreSQL + pgvector)

The database runs in Docker. The `docker-compose.yml` at the project root starts it:

```bash
# From the medBook/ root
docker compose up -d

# Or start the named container directly
docker start mednotebook-postgres
```

Connection details (for pgAdmin or any DB client):

| Setting | Value |
|---------|-------|
| Host | `localhost` |
| Port | `5433` (not 5432 — avoids conflict with other containers) |
| Database | `mednotebook_dev` |
| Username | `mednotebook_user` |
| Password | `mednotebook_pass` |

---

## Stubbed vs Fully Implemented

### Fully implemented

| Feature | Notes |
|---------|-------|
| Database schema | All 7 tables created via Alembic; pgvector extension enabled |
| Pydantic schemas | All request/response types with validation — password min 8 + digit, project name max 100, file max 50 MB |
| Request logging | Every request logs `request_id METHOD /path - STATUS - Xms`; `X-Request-ID` on every response |
| CORS | Configured from `ALLOWED_ORIGINS` env var |
| Error handlers | 404 → `NOT_FOUND`, 422 → clean field-level list, 500 → logs traceback, hides raw exception; `AppException` for app-level errors |
| Health endpoints | `/health` and `/health/db` (real DB ping) |
| API routing | All 27 endpoints registered under `/api/v1` with correct HTTP methods and status codes |
| Frontend API client | `lib/api.ts` — typed `get/post/patch/del`, auto auth header, 401 redirect |
| API status indicator | Green/red dot in TopBar — visible in development only |

### Stubbed (placeholder responses — real logic in future sessions)

| Feature | Stubbed behaviour | Session |
|---------|-------------------|---------|
| `POST /auth/register` | Returns hardcoded user — no DB write | 4 |
| `POST /auth/login` | Returns `"placeholder-access-token"` — no credential check | 4 |
| `POST /auth/refresh` | Returns same placeholder token | 4 |
| `POST /auth/logout` | Returns `{message: "logged out"}` — no token blacklist | 4 |
| `GET /users/me` | Returns hardcoded "John Doe" — no JWT extraction | 4 |
| All `GET` list endpoints | Return `[]` — no DB queries | 4 |
| All `POST/PATCH/DELETE` endpoints | Echo back or return placeholder data — no DB writes | 4 |
| `POST /documents/upload` | Returns placeholder `DocumentResponse` — no S3 upload | 5 |
| `GET /documents/{id}/chunks` | Always returns `[]` | 5 |
| `POST /documents/{id}/summarize` | Returns `202 Accepted` — no job queued | 6 |
| `POST /queries` | Returns placeholder with `answer: null` — no AI call | 6 |

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env`. Current status:

| Variable | Status | Notes |
|----------|--------|-------|
| `DATABASE_URL` | ✅ Set | Points to Docker container on port 5433 |
| `SECRET_KEY` | ⚠️ Change before prod | Current value is a placeholder string |
| `ALGORITHM` | ✅ Set | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | ✅ Set | 60 minutes |
| `REFRESH_TOKEN_EXPIRE_DAYS` | ✅ Set | 30 days |
| `AWS_ACCESS_KEY_ID` | ❌ Needs real value | Required for Session 5 (file upload) |
| `AWS_SECRET_ACCESS_KEY` | ❌ Needs real value | Required for Session 5 (file upload) |
| `AWS_BUCKET_NAME` | ❌ Needs real value | Create an S3 bucket before Session 5 |
| `AWS_REGION` | ✅ Set | `us-east-1` (change if using a different region) |
| `ANTHROPIC_API_KEY` | ❌ Needs real value | Required for Session 6 (AI queries) |
| `ENVIRONMENT` | ✅ Set | `development` |
| `ALLOWED_ORIGINS` | ✅ Set | `http://localhost:3000,http://localhost:3001` |
| `MAX_UPLOAD_SIZE_MB` | ✅ Set | 50 MB |
| `RATE_LIMIT_PER_MINUTE` | ✅ Set | 60 requests/min (not enforced yet) |

To generate a strong `SECRET_KEY`:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## Frontend Changes (Session 3)

Three new frontend files connect the UI to the backend:

| File | What it does |
|------|--------------|
| `frontend/lib/api.ts` | Typed fetch client — `api.get/post/patch/del`; auto-injects `Authorization: Bearer <token>` from localStorage; clears token and redirects to `/login` on 401 |
| `frontend/.env.local` | `NEXT_PUBLIC_API_URL=http://localhost:8001/api/v1` and `NEXT_PUBLIC_ENVIRONMENT=development` |
| `frontend/components/ui/ApiStatus.tsx` | Green/red dot in the TopBar — calls `/health` on mount; only visible when `NEXT_PUBLIC_ENVIRONMENT=development` |

---

## Session 04 — What Gets Built Next

**JWT Authentication** — replacing all placeholder responses with real behaviour:

- Hash passwords with bcrypt on register; verify on login
- Issue real JWTs (access token + refresh token) signed with `SECRET_KEY`
- `get_current_user` dependency that validates Bearer tokens on every protected route
- All list endpoints filter by the authenticated user
- All write endpoints associate records with the authenticated user
- Refresh token rotation
- Route protection middleware on the frontend (`/dashboard/*` redirects to `/login` if no token)
