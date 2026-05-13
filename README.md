# MedNotebook

A secure AI-powered document workspace for medical researchers and biology students.

## What it does

Users upload documents (PDFs, CSVs, images, text files). The app extracts the text, stores it, and lets users ask AI-powered questions about their documents — with answers that include source citations.

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js (React) |
| Backend | Python + FastAPI |
| Database | PostgreSQL + pgvector |
| File Storage | AWS S3 |
| AI | Claude API (Anthropic) |

## Project Structure

```
medBook/
├── frontend/   # Next.js web app
├── backend/    # FastAPI Python server
├── docs/       # Project notes and documentation
├── README.md
└── .gitignore
```

## Getting Started

See `frontend/README.md` and `backend/README.md` for setup instructions for each service.
