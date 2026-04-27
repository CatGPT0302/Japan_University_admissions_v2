# admissions_v2

An LLM-assisted information extraction and validation system for Japanese university admission guideline PDFs (especially 留学生募集要項).

## Project Positioning

This project is **not** a pure OCR or PDF vision engine project.

The goal is to use LLM/Agent-based reading to extract key admission information from PDFs and structure it into human-verifiable data workflows (CSV/JSON/table views).

## Input / Output

- Input: Japanese university admission PDFs
- Output: structured admission records for staging/confirmation/export

## Current Focus

- Improve snippet quality and traceability (`trace_debug.json`)
- Improve field-to-snippet matching
- Keep sample size fixed during this stage

## Current Status

- First traceability spike is complete.
- Technical direction is validated.
- Main bottleneck is snippet quality (not sample volume).
- Internal demo is possible, but this is **not production-ready** yet.

## Repository Components

- API backend: `scripts/api.py` (FastAPI)
- Internal review app: `scripts/app.py` (Streamlit)
- Extraction entry: `scripts/extract_direct.py`
- React demo frontend: `frontend/`
- SQLite runtime DB: `database/admissions_v2.db`

## Quick Start

### Backend

```powershell
cd C:\Users\a3513\Desktop\日本大学招生系统项目\admissions_v2
python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd C:\Users\a3513\Desktop\日本大学招生系统项目\admissions_v2\frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment

Use `.env.example` in project root and `frontend/.env.example` for frontend base URL.

Required:
- `OPENAI_API_KEY`

Optional:
- `OPENAI_TEXT_MODEL`
- `OPENAI_VISION_MODEL`

## Documentation

- `docs/handoff.md`
- `docs/phase2_ui.md`
- `docs/leader_demo.md`
- `TODO.md`

## For Future Agents

If you are an AI coding agent or a new developer continuing this project, start with:

- `docs/AGENT_BOOTSTRAP.md`
- `docs/NEXT_AGENT_PROMPT.md`
- `docs/PROJECT_CHECKPOINT.md`

Do not start by rewriting the pipeline. The current priority is snippet quality and traceability.
