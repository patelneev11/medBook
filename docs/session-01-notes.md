# Session 01 — Project Scaffold

## What Was Built

- Initialized the full MedNotebook project structure from scratch
- Set up a Next.js 16 frontend with TypeScript, Tailwind CSS, and App Router
- Set up a Python FastAPI backend with a virtual environment and all core dependencies installed
- Added a placeholder home page ("MedNotebook — Coming soon")
- Added a working `GET /` health-check endpoint on the backend
- Created a root `.gitignore` covering `node_modules`, `venv`, `.env`, and `__pycache__`
- Made the first git commit with all 27 project files

---

## Folder Structure

```
medBook/
├── .gitignore
├── CLAUDE.md                  # Guidance for Claude Code
├── README.md                  # Project overview
├── docs/
│   ├── notes.md               # Open decisions and questions
│   └── session-01-notes.md    # This file
├── frontend/                  # Next.js app
│   ├── app/
│   │   ├── globals.css
│   │   ├── layout.tsx
│   │   └── page.tsx           # "Coming soon" placeholder
│   ├── public/
│   ├── package.json
│   ├── tsconfig.json
│   └── next.config.ts
└── backend/                   # FastAPI app
    ├── main.py                # App entrypoint, GET / endpoint
    ├── requirements.txt       # Python dependencies
    ├── .env.example           # Environment variable template
    └── venv/                  # Python virtual environment (not in git)
```

---

## How to Start the Frontend

```bash
cd /Users/ankurp/Documents/git/medBook/frontend
npm run dev
```

URL: **http://localhost:3001** (port 3000 is occupied by another process on this machine)

---

## How to Start the Backend

```bash
cd /Users/ankurp/Documents/git/medBook/backend
source venv/bin/activate
uvicorn main:app --reload
```

URL: **http://localhost:8000**  
API docs: **http://localhost:8000/docs**  
Expected response at `/`: `{"status":"ok","app":"MedNotebook API"}`

---

## Environment Variables Still Needed

Copy `backend/.env.example` to `backend/.env` and fill in these values before the app can connect to real services:

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | PostgreSQL connection string (needs a running Postgres instance with pgvector) |
| `AWS_ACCESS_KEY_ID` | AWS credentials for S3 file uploads |
| `AWS_SECRET_ACCESS_KEY` | AWS credentials for S3 file uploads |
| `AWS_BUCKET_NAME` | The S3 bucket where uploaded files will be stored |
| `ANTHROPIC_API_KEY` | Claude API key for AI-powered document Q&A |

---

## Session 02 — What Gets Built Next

The frontend skeleton:

- Login page (`/login`)
- Dashboard page (`/dashboard`) — protected, only accessible when logged in
- Basic navigation layout shared across pages
- Authentication flow (to be decided: Auth0, Clerk, or custom JWT)
