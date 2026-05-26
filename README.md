# admissions_v2

## Project Overview

admissions_v2 is an owner-hosted Japanese university admissions system.

It has three product surfaces:

- Owner/admin workspace: upload admissions PDFs or source URLs, run extraction, review uncertain content, confirm records, and export the master Excel workbook.
- Partner service center: issue limited access, receive submitted PDFs or links, track processing progress, and keep final data confirmation under the owner.
- Student/parent frontend: collect a student's profile, show schools worth checking, explain requirements in plain language, and accept consultation bookings.

The project is not a pure OCR tool and is no longer only a local extraction MVP. The core data and extraction workflow stay owner-controlled.

## Current Workflow

```text
Partner user or owner submits source material
-> system stores the submission
-> owner starts the existing extraction workflow
-> extracted content enters review
-> owner confirms it into the main database
-> student frontend and licensed API read confirmed data only
```

## Product Websites

Use separate deployments/sites for the three systems. They can share this repository and backend, but they should not be exposed as different hash routes on one public URL.

- Owner data workspace site: `VITE_APP_SURFACE=owner`
- Owner partner-management site: `VITE_APP_SURFACE=owner-service`
- Partner service center site: `VITE_APP_SURFACE=partner`
- Student/parent frontend site: `VITE_APP_SURFACE=student`

`VITE_APP_SURFACE=combined` is only for local debugging. Do not use it as the public product entry.

## Backend Interfaces

- Admin workflow: `/upload`, `/agent/run`, `/staging/*`, `/confirm/*`, `/records`, `/export/excel`
- Public student API: `/public/programs`, `/public/recommendations`, `/public/bookings`
- Licensed API: `/v1/programs`, `/v1/recommendations`, `/v1/bookings`, `/v1/documents/submissions`
- Owner queue: `/admin/submissions`

Licensed API keys are stored as hashes. The full secret is only shown once when created.

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

For local split-site testing, run separate Vite servers with different surfaces:

```powershell
$env:VITE_API_BASE_URL="http://127.0.0.1:8000"
$env:VITE_APP_SURFACE="owner"; npm run dev -- --host 127.0.0.1 --port 5173
$env:VITE_APP_SURFACE="owner-service"; npm run dev -- --host 127.0.0.1 --port 5174
$env:VITE_APP_SURFACE="partner"; npm run dev -- --host 127.0.0.1 --port 5175
$env:VITE_APP_SURFACE="student"; npm run dev -- --host 127.0.0.1 --port 5176
```

For the owner partner-management site, set `VITE_OWNER_WORKSPACE_URL` to the separate owner data workspace URL. This lets the partner-management site send the owner back to the review workspace after a submitted source has been processed.

## Environment Variables

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

## Data Boundary

This repository is designed for public admissions information, official university publications, publicly available admissions documents, and manually prepared sample data.

Do not commit private datasets, real student information, private operational data, secrets, or customer-specific files.

Owner data assets remain in the owner-hosted database. Partner users receive limited use rights through issued access, not ownership of the master database or extraction logic.

## Verification

```powershell
python -m pytest -q
cd frontend
npm run build
npm run smoke:surfaces
npm run smoke:browser
```

`smoke:browser` uses the local Chrome or Edge installation, starts a temporary SQLite-backed API, signs into the owner and partner surfaces with throwaway accounts, and checks that the owner, owner-service, partner, and student surfaces stay separated in real browser pages.
Run the two frontend smoke commands one after another because both rebuild `frontend/dist`.

## Ownership

See `OWNERSHIP.md`.
