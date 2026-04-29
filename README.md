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

Field governance baseline is documented in `FIELD_HIGHEST_PRINCIPLE.md` and must be followed for extraction and review UI updates.

## Project Positioning

This project is not a pure OCR or PDF vision engine project.

The goal is to use LLM- and agent-assisted reading to extract key admission information from PDFs and structure it into human-verifiable workflows for staging, confirmation, and export.

The frozen MVP delivery scope is:

```text
募集要項 PDF
→ extract_fields.py
→ normalize_fields.py
→ staging / confirmed records
→ export_excel.py standard Excel master table
```

Final acceptance rules and future-agent backend/frontend prompts are documented in `docs/FINAL_ACCEPTANCE_AND_AGENT_PROMPTS.md`.

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

### MVP Extraction And Export

Extract fields from any 募集要項 PDF:

```powershell
python scripts/extract_fields.py <pdf_path> --output output.json
```

Export the normalized fixed-column TSV:

```powershell
python scripts/export_tsv.py output.json --output admissions_standard.tsv
```

Export the polished Excel master table:

```powershell
python scripts/export_excel.py output.json --output admissions_standard.xlsx
```

Export confirmed records from the current database:

```powershell
python scripts/export_excel.py --from-db --output admissions_master.xlsx
```

## Environment

Use `.env.example` in the project root and `frontend/.env.example` for the frontend base URL.

Required:

- `OPENAI_API_KEY` (or `LLM_API_KEY`)

Optional:

- `OPENAI_TEXT_MODEL`
- `OPENAI_VISION_MODEL`
- `OPENAI_BASE_URL` or `LLM_BASE_URL` (OpenAI-compatible base URL)
- `OPENAI_COMPAT_URL` or `LLM_COMPAT_URL` (full chat completions URL; higher priority than base URL)

Compatibility resolution order:

- API key: `LLM_API_KEY` -> `OPENAI_API_KEY`
- Endpoint: `OPENAI_COMPAT_URL` -> `LLM_COMPAT_URL` -> `OPENAI_URL` -> `OPENAI_BASE_URL` -> `LLM_BASE_URL` -> official OpenAI default

## PDF Source Registry

For stable PDF retrieval, you can maintain your own source registry at `private_data/pdf_source_registry.csv`.

The repository includes `data/sample_pdf_source_registry.csv` only as a replaceable demonstration sample.

Use `data/pdf_source_registry.template.csv` as the starting template for a real maintained registry.

When a registry entry matches a university and year, the system will prefer that maintained source before falling back to open-web search.

## Quality Ops Endpoints

These endpoints are intended for quality control and operational monitoring:

- `GET /metrics/quality`
  - Returns field coverage, field-level manual-modification rates, risk distribution, and confidence calibration buckets.
  - Optional query: `doc_id=<int>` for document-level metrics.
- `GET /metrics/corrections`
  - Returns correction events generated from human `PATCH /staging/{id}` updates.
  - Optional query: `doc_id=<int>`, `limit=<int>`.
- `GET /fetch-pdf/probe?year=2026`
  - Probes maintained target pages and reports possible new PDF candidates not yet in the registry.

## Golden Sample Regression

Run lightweight regression reporting:

```powershell
python scripts/regression_golden_samples.py
```

Optional full rerun and report save:

```powershell
python scripts/regression_golden_samples.py --run-extract --save-json .\demo\golden_report.json
```

For standalone source probing (cron/scheduler-friendly):

```powershell
python scripts/probe_pdf_sources.py --year 2026 --save-json .\demo\probe_report.json
```

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
