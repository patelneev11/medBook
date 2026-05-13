# MedNotebook — Backend

FastAPI Python server for MedNotebook.

## Setup

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload
```

## Environment Variables

Create a `.env` file:

```
DATABASE_URL=postgresql://user:password@localhost:5432/mednotebook
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_S3_BUCKET=
ANTHROPIC_API_KEY=
```
