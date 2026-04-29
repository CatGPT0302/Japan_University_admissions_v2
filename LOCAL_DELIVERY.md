# Local Delivery Guide

This project is now treated as a local-first internal tool.

The expected local flow is:

```text
募集要項 PDF
→ local backend at http://127.0.0.1:8000
→ local frontend at http://127.0.0.1:5173
→ staging / confirmed records in the local database
→ standard Excel master export
```

## One-Time Setup

Run:

```powershell
.\setup_once.bat
```

Then edit `.env` and set one of:

```text
LLM_API_KEY=
OPENAI_API_KEY=
```

Optional OpenAI-compatible provider settings:

```text
LLM_BASE_URL=
OPENAI_BASE_URL=
LLM_COMPAT_URL=
OPENAI_COMPAT_URL=
OPENAI_TEXT_MODEL=
OPENAI_VISION_MODEL=
```

## Daily Startup

Run:

```powershell
.\start_all.bat
```

This starts:

```text
Backend:  http://127.0.0.1:8000
Frontend: http://127.0.0.1:5173
```

`start_all.bat` also rewrites `frontend/.env` to use the local backend. This file is intentionally not committed.

## Delivery Boundary

Deliver the local tool and outputs, not cloud credentials.

Do not deliver or commit:

```text
.env
API keys
local database files
node_modules
frontend/dist
temporary JSON / TSV / XLSX
rendered PDF images
input PDFs unless explicitly approved
```

Useful deliverables:

```text
standard Excel export
screenshots
limited local demo
README / LOCAL_DELIVERY guide
```

## Smoke Test

Check backend:

```powershell
python -c "import scripts.api"
```

Check frontend:

```powershell
cd frontend
npm run build
```

Check standard export:

```powershell
python scripts/export_excel.py demo/waseda_symbol_extract.json --output demo/waseda_standard.xlsx
```

If `demo/waseda_symbol_extract.json` is unavailable, run the export command against any valid `extract_fields.py` output JSON.
