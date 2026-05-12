# admissions_v2

## Project Overview

admissions_v2 is an LLM-assisted admissions information extraction and review system for Japanese university admission guideline PDFs.

The project focuses on turning public admission documents into structured, human-reviewable records. It is not a pure OCR project and it is not a general-purpose PDF parser.

## Core Workflow

```text
PDF upload / source input
-> field extraction
-> normalization
-> staging review
-> confirmed records
-> Excel master export
```

## Features

- PDF upload and source input
- Public-source PDF retrieval and maintained source registry support
- LLM-assisted field extraction
- Field evidence, confidence, risk level, and warnings
- Staging review before records are confirmed
- Confirmed records database
- Standard Excel master export
- Quality metrics and correction history endpoints

## Tech Stack

- Backend: Python, FastAPI
- Frontend: React, TypeScript, Vite
- Database: SQLite for local use, PostgreSQL-compatible deployment option
- Export: openpyxl
- LLM: OpenAI-compatible chat completion API

## Local Setup

### Backend

```powershell
cd <project-root>
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd <project-root>\frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

The frontend should point to the local backend:

```text
VITE_API_BASE_URL=http://127.0.0.1:8000
```

### Environment Variables

Use `.env.example` in the project root and `frontend/.env.example` for local configuration templates.

Required for extraction:

- `OPENAI_API_KEY` or `LLM_API_KEY`

Optional:

- `OPENAI_TEXT_MODEL`
- `OPENAI_VISION_MODEL`
- `OPENAI_BASE_URL` or `LLM_BASE_URL`
- `OPENAI_COMPAT_URL` or `LLM_COMPAT_URL`

Resolution order:

- API key: `LLM_API_KEY` -> `OPENAI_API_KEY`
- Endpoint: `OPENAI_COMPAT_URL` -> `LLM_COMPAT_URL` -> `OPENAI_URL` -> `OPENAI_BASE_URL` -> `LLM_BASE_URL` -> official OpenAI default

## Extraction And Export

Extract fields from a Japanese university admission PDF:

```powershell
python scripts/extract_fields.py <pdf_path> --output output.json
```

Export a normalized TSV:

```powershell
python scripts/export_tsv.py output.json --output admissions_standard.tsv
```

Export an Excel master workbook:

```powershell
python scripts/export_excel.py output.json --output admissions_standard.xlsx
```

Export confirmed records from the current database:

```powershell
python scripts/export_excel.py --from-db --output admissions_master.xlsx
```

## Data Boundary

This repository is designed for public admission information, official university publications, publicly available admission documents, and manually prepared sample data.

It does not include private datasets, confidential documents, real student information, private operational data, or non-public reference tables.

Runtime data that is private, custom, or maintained by a user should stay outside the public repository, for example under `private_data/` or another user-controlled path that is not committed.

## Current Status

The project is an MVP-stage local workflow tool for controlled demos, validation, and extraction-quality iteration.

The current engineering priority is extraction quality, evidence traceability, and human review efficiency. It should not be described as a production SaaS system.

## Documentation

- `docs/AGENT_BOOTSTRAP.md`
- `docs/handoff.md`
- `docs/phase2_ui.md`
- `docs/leader_demo.md`
- `docs/FINAL_ACCEPTANCE_AND_AGENT_PROMPTS.md`
- `TODO.md`

## Ownership

See `OWNERSHIP.md`.
