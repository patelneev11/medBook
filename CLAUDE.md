# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

MedNotebook — a secure AI-powered document workspace for medical researchers and biology students. Users upload files (PDFs, CSVs, images, text), the app extracts text, stores it with vector embeddings, and answers AI-powered questions with source citations.

## Architecture

```
frontend/   → Next.js (React) — user interface
backend/    → Python FastAPI  — REST API, document processing, AI queries
```

**Data flow:** User uploads file → S3 (raw storage) → backend extracts text → chunks text → generates embeddings via Claude → stores in PostgreSQL (pgvector) → user asks question → vector similarity search retrieves relevant chunks → Claude API generates answer with citations.

## Tech Stack

- **Frontend:** Next.js (React)
- **Backend:** Python + FastAPI
- **Database:** PostgreSQL with pgvector extension
- **File storage:** AWS S3
- **AI:** Claude API (Anthropic)
- **Vector search:** pgvector

## Development

### Frontend
```bash
cd frontend
npm install
npm run dev        # dev server at localhost:3000
npm run build      # production build
npm run lint       # ESLint
```

### Backend
```bash
cd backend
source venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload    # dev server at localhost:8000
pytest                       # run all tests
pytest tests/test_foo.py     # run a single test file
```

## Environment Variables

**Frontend** (`.env.local`):
- `NEXT_PUBLIC_API_URL` — backend API base URL

**Backend** (`.env`):
- `DATABASE_URL` — PostgreSQL connection string
- `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET`
- `ANTHROPIC_API_KEY`
