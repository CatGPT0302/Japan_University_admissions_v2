from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import extract_direct as extract_direct  # noqa: E402
from scripts.db import (  # noqa: E402
    confirm_all_by_doc,
    delete_staging_record,
    get_records,
    get_stats as db_get_stats,
    get_staging_record,
    get_staging_records,
    init_db,
    insert_staging_record,
    update_staging_record,
)
from scripts.validator import validate  # noqa: E402

INPUT_DIR = ROOT / "input_pdfs"
INPUT_DIR.mkdir(parents=True, exist_ok=True)


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    }
    for value in raw.split(","):
        value = value.strip().rstrip("/")
        if value:
            origins.add(value)
    for name in ("FRONTEND_URL", "VITE_APP_URL"):
        value = os.environ.get(name, "").strip().rstrip("/")
        if value:
            origins.add(value)
    vercel_url = os.environ.get("VERCEL_URL", "").strip()
    if vercel_url:
        origins.add(f"https://{vercel_url.rstrip('/')}")
    return sorted(origins)

app = FastAPI(title="admissions_v2 API", version="1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()


class ExtractRequest(BaseModel):
    file_name: str
    university: str
    year: str
    url: str | None = ""


class PatchRequest(BaseModel):
    data: dict[str, Any]


class RecordsQuery(BaseModel):
    university: str | None = None
    year: int | None = None
    faculty: str | None = None
    limit: int = 100
    offset: int = 0


class ManualRecord(BaseModel):
    document_id: int
    data: dict[str, Any]


def _run_extract_direct(file_name: str, university: str, year: str, url: str = "") -> dict[str, Any]:
    pdf_path = INPUT_DIR / file_name
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {file_name}")
    try:
        return extract_direct.run_extraction(
            pdf_path=pdf_path,
            university=university,
            year=str(year),
            url=url or "",
        )
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail=f"PDF not found: {file_name}")
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "extract_direct failed",
                "message": str(exc),
            },
        )


@app.post("/upload")
async def upload_pdf(file: UploadFile = File(...)) -> dict[str, str]:
    suffix = Path(file.filename or "").suffix or ".pdf"
    saved_name = Path(file.filename or "uploaded.pdf").name
    save_path = INPUT_DIR / saved_name
    content = await file.read()
    save_path.write_bytes(content)
    return {
        "file_name": saved_name,
        "saved_path": str(save_path),
    }


@app.post("/extract")
def extract_pdf(payload: ExtractRequest) -> dict[str, Any]:
    result = _run_extract_direct(payload.file_name, payload.university, payload.year, payload.url or "")
    return {
        "doc_id": result.get("doc_id"),
        "status": result.get("status"),
        "records": result.get("records"),
        "failed_pages": result.get("failed_pages", []),
    }


@app.get("/staging/{doc_id}")
def list_staging(doc_id: int) -> list[dict[str, Any]]:
    records = get_staging_records(doc_id)
    fields = [
        "id", "document_id", "page_number",
        "university", "admission_year", "admission_period",
        "faculty", "department", "application_period", "deadline_rule",
        "eju_session", "eju_japanese", "eju_general", "eju_math",
        "eju_physics", "eju_chemistry", "eju_biology",
        "english_requirement", "screening_method", "screening_schedule",
        "result_date", "enrollment_period", "prefecture", "campus",
        "confidence", "needs_review", "is_confirmed", "updated_at",
    ]
    return [{k: rec.get(k) for k in fields} for rec in records]


@app.patch("/staging/{staging_id}")
def patch_staging(staging_id: int, payload: PatchRequest) -> dict[str, Any]:
    updated = update_staging_record(staging_id, payload.data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"staging record not found: {staging_id}")
    return updated


@app.delete("/staging/{staging_id}")
def delete_staging(staging_id: int) -> dict[str, Any]:
    row = get_staging_record(staging_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    delete_staging_record(staging_id)
    return {"status": "deleted", "id": staging_id}


@app.post("/staging/manual")
def create_manual_staging(payload: ManualRecord) -> dict[str, Any]:
    record = dict(payload.data or {})
    validated = validate(record)
    row_id = insert_staging_record(payload.document_id, None, validated)
    return {"id": row_id, "status": "created"}


@app.post("/confirm/{doc_id}")
def confirm_doc(doc_id: int) -> dict[str, int]:
    stats = confirm_all_by_doc(doc_id)
    return {
        "confirmed": int(stats.get("written", 0)),
        "skipped": int(stats.get("skipped", 0)),
    }


@app.get("/records")
def list_records(
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    rows = get_records(
        university=university,
        year=year,
        faculty=faculty,
        limit=limit,
        offset=offset,
    )
    return rows


@app.get("/stats")
def get_stats() -> dict[str, Any]:
    return db_get_stats()


@app.get("/export/excel")
def export_excel(
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
) -> StreamingResponse:
    """Export confirmed records as .xlsx file."""
    import io

    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError:
        raise HTTPException(status_code=500, detail="openpyxl not installed: pip install openpyxl")

    rows = get_records(university=university, year=year, faculty=faculty, limit=10000, offset=0)
    if not rows:
        raise HTTPException(status_code=404, detail="No records found for the given filters")

    wb = Workbook()
    ws = wb.active
    ws.title = "募集要項"

    # Header columns
    columns = [
        ("id", 6),
        ("university", 18),
        ("admission_year", 10),
        ("faculty", 20),
        ("department", 24),
        ("admission_period", 12),
        ("application_period", 22),
        ("english_requirement", 30),
        ("screening_method", 24),
        ("result_date", 16),
        ("prefecture", 10),
        ("campus", 14),
    ]
    header_font = Font(bold=True, color="FFFFFF", size=11)
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")

    for col_idx, (col_name, width) in enumerate(columns, start=1):
        cell = ws.cell(row=1, column=col_idx, value=col_name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        ws.column_dimensions[cell.column_letter].width = width

    # Data rows
    for row_idx, record in enumerate(rows, start=2):
        for col_idx, (col_name, _) in enumerate(columns, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=record.get(col_name, ""))
            cell.alignment = Alignment(wrap_text=True, vertical="top")

    ws.auto_filter.ref = ws.dimensions
    ws.freeze_panes = "A2"

    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)

    filename = "admissions_v2_export.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.xml",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
