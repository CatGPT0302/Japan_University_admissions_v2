# admissions_v2

An LLM-assisted information extraction and validation system for Japanese university admission guideline PDFs, especially foreign-student admissions materials.

## Ownership / Usage Notice

This is a personal project independently developed and maintained by the author.

It is not affiliated with, sponsored by, commissioned by, or owned by any organization.

Any organization may only use this tool under explicit permission from the author.

Source code, deployment credentials, database schema, prompts, extraction workflow, and review logic remain the author's intellectual assets unless otherwise agreed in writing.

## Data & Ownership Notice

The repository does not include proprietary datasets, internal company documents, or third-party confidential materials.

Any sample data included in this repository is for demonstration only and should be replaceable by users' own public-source data.

The codebase, extraction workflow, review workflow, confidence/evidence/risk logic, UI design, and product structure are maintained as the author's personal work.

Third-party datasets or organization-specific templates, if any, must not be committed to this repository.

## Project Positioning

This project is not a pure OCR or PDF vision engine project.

The goal is to use LLM- and agent-assisted reading to extract key admission information from PDFs and structure it into human-verifiable workflows for staging, confirmation, and export.

## Input / Output

- Input: Japanese university admission PDFs
- Output: structured admission records for staging, confirmation, search, and export

## Current Focus

- Improve snippet quality and traceability
- Improve field-to-snippet matching
- Keep validation quality ahead of feature expansion

## Current Status

- The cloud demo and review workflow are available
- The technical direction is validated
- The current bottleneck is extraction quality and source-PDF stability, not UI availability
- The system is suitable for controlled demos and validation, but it is not a general-purpose production service

## Repository Components

- API backend: `scripts/api.py`
- Review app: `scripts/app.py`
- Extraction entry: `scripts/extract_direct.py`
- React frontend: `frontend/`
- Runtime database is created locally at runtime and is not part of the default deliverable scope

## Schema Note

The admissions_v2 data structure is designed around public admissions-PDF information and the system's own review workflow needs.

The working schema includes standardized operational fields such as `field_confidence`, `field_evidence`, `risk_level`, `manual_modified_fields`, review-status flags, and source-document linkage.

It should not be described as an organization-specific template.

## Quick Start

### Backend

```powershell
cd <project-root>
python -m uvicorn scripts.api:app --reload --host 127.0.0.1 --port 8000
```

### Frontend

```powershell
cd <project-root>\frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## Environment

Use `.env.example` in the project root and `frontend/.env.example` for the frontend base URL.

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

If you are continuing this project, start with:

- `docs/AGENT_BOOTSTRAP.md`
- `docs/NEXT_AGENT_PROMPT.md`
- `docs/PROJECT_CHECKPOINT.md`

Do not start by rewriting the pipeline. The current priority is quality control, traceability, and controlled review efficiency.
