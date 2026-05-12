from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import fetch_pdfs as fetch_pdfs  # noqa: E402
from scripts import full_vision_extractor as full_vision_extractor  # noqa: E402
from scripts.db import (  # noqa: E402
    confirm_all_by_doc,
    delete_document,
    delete_staging_record,
    get_correction_events as db_get_correction_events,
    get_db_runtime,
    get_document_file as db_get_document_file,
    get_documents as db_get_documents,
    get_document_summary as db_get_document_summary,
    get_quality_metrics as db_get_quality_metrics,
    get_records,
    get_stats as db_get_stats,
    get_staging_record,
    get_staging_records,
    init_db,
    insert_staging_record,
    update_staging_record,
)
from scripts.export_excel import export_excel_bytes_from_records  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.runtime_paths import ensure_runtime_dirs, frontend_dist_dir, rendered_pages_dir, uploads_dir  # noqa: E402
from scripts.validator import validate  # noqa: E402

ensure_runtime_dirs()
INPUT_DIR = uploads_dir()
INPUT_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST_DIR = frontend_dist_dir()


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

app = FastAPI(title="日本大学招生要项全卷视觉工作台 API", version="1.0")
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
    university: str = ""
    year: str
    url: str | None = ""


class PatchRequest(BaseModel):
    data: dict[str, Any]


class FetchPdfRequest(BaseModel):
    university: str
    year: str = "2026"
    page_url: str | None = ""
    pdf_url: str | None = ""


class SearchPdfRequest(BaseModel):
    university: str
    year: str = "2026"
    page_url: str | None = ""


class RecordsQuery(BaseModel):
    university: str | None = None
    year: int | None = None
    faculty: str | None = None
    limit: int = 100
    offset: int = 0


class ManualRecord(BaseModel):
    document_id: int
    data: dict[str, Any]


class DocumentsQuery(BaseModel):
    q: str | None = None
    year: str | None = None
    limit: int = 100
    offset: int = 0


def _run_extract_direct(file_name: str, university: str, year: str, url: str = "") -> dict[str, Any]:
    pdf_path = INPUT_DIR / file_name
    if not pdf_path.exists():
        raise HTTPException(status_code=404, detail=f"PDF not found: {file_name}")
    try:
        return full_vision_extractor.run_extraction(
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
                "error": "full_vision_extractor failed",
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


@app.get("/", response_model=None)
def root() -> Any:
    index_path = FRONTEND_DIST_DIR / "index.html"
    if index_path.exists():
        return FileResponse(index_path)
    return {"status": "ok", "service": "admissions_v2"}


@app.get("/health")
def health() -> dict[str, Any]:
    runtime = get_db_runtime()
    return {
        "status": "healthy",
        "db_mode": runtime.mode,
        "db_source": runtime.source,
        "db_persistent": runtime.persistent,
        "db_warning": runtime.warning,
    }


@app.post("/extract")
def extract_pdf(payload: ExtractRequest) -> dict[str, Any]:
    result = _run_extract_direct(payload.file_name, payload.university, payload.year, payload.url or "")
    return {
        "doc_id": result.get("doc_id"),
        "status": result.get("status"),
        "university": result.get("university", ""),
        "records": result.get("records"),
        "failed_pages": result.get("failed_pages", []),
        "quality_status": result.get("quality_status", "needs_review"),
        "quality_message": result.get("quality_message", ""),
        "warnings": result.get("warnings", []),
    }


@app.post("/extract/full-vision")
def extract_pdf_full_vision(payload: ExtractRequest) -> dict[str, Any]:
    return extract_pdf(payload)


@app.get("/fetch-pdf/targets")
def fetch_pdf_targets() -> list[dict[str, str]]:
    return fetch_pdfs.list_targets()


@app.post("/fetch-pdf/search")
def search_pdf(payload: SearchPdfRequest) -> dict[str, Any]:
    try:
        return fetch_pdfs.search_single(
            university=payload.university,
            year=int(payload.year or "2026"),
            page_url=payload.page_url or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "search_pdf failed",
                "message": str(exc),
            },
        )


@app.get("/fetch-pdf/probe")
def probe_pdf_sources(year: int = 2026) -> dict[str, Any]:
    try:
        return fetch_pdfs.probe_targets(year=year)
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "probe_pdf_sources failed",
                "message": str(exc),
            },
        )


@app.post("/fetch-pdf")
def fetch_pdf(payload: FetchPdfRequest) -> dict[str, Any]:
    try:
        result = fetch_pdfs.fetch_single(
            university=payload.university,
            year=int(payload.year or "2026"),
            page_url=payload.page_url or "",
            pdf_url=payload.pdf_url or "",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "fetch_pdf failed",
                "message": str(exc),
            },
        )

    if result.get("status") != "downloaded":
        raise HTTPException(status_code=404, detail=result)

    return result


@app.get("/documents")
def list_documents(
    q: str | None = None,
    year: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return db_get_documents(query=q, year=year, limit=limit, offset=offset)


@app.get("/documents/{doc_id}/summary")
def get_document_summary(doc_id: int) -> dict[str, Any]:
    row = db_get_document_summary(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return row


@app.get("/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: int) -> FileResponse:
    pdf_path = _document_pdf_path(doc_id)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.get("/documents/{doc_id}/page-image")
def get_document_page_image(doc_id: int, page: int = 1) -> FileResponse:
    pdf_path = _document_pdf_path(doc_id)
    page_num = max(int(page or 1), 1)
    out_dir = rendered_pages_dir() / f"preview_{doc_id}"
    image_path = out_dir / f"page_{page_num:03d}.png"
    if not image_path.exists():
        rendered = render_pdf_to_images(pdf_path, out_dir, dpi=180, pages=[page_num])
        if not rendered:
            raise HTTPException(status_code=404, detail="PDF page not found")
        image_path = rendered[0]
    return FileResponse(image_path, media_type="image/png")


def _document_pdf_path(doc_id: int) -> Path:
    row = db_get_document_file(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    raw_path = str(row.get("file_path") or "").strip()
    filename = str(row.get("filename") or f"document_{doc_id}.pdf")
    candidates = []
    if raw_path:
        candidates.append(Path(raw_path))
    candidates.append(INPUT_DIR / filename)
    pdf_path = next((path for path in candidates if path.exists() and path.is_file()), None)
    if not pdf_path:
        raise HTTPException(status_code=404, detail="PDF file not found")
    return pdf_path


@app.delete("/documents/{doc_id}")
def delete_uploaded_document(doc_id: int) -> dict[str, Any]:
    result = delete_document(doc_id)
    if not result:
        raise HTTPException(status_code=404, detail="document not found")
    return {"status": "deleted", **result}


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
        "field_confidence", "field_evidence", "risk_level",
        "manual_modified_fields", "is_reviewed", "reviewed_at", "warnings_json",
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
    runtime = get_db_runtime()
    stats = db_get_stats()
    stats.update(
        {
            "db_mode": runtime.mode,
            "db_source": runtime.source,
            "db_persistent": runtime.persistent,
            "db_warning": runtime.warning,
        }
    )
    return stats


@app.get("/metrics/quality")
def quality_metrics(doc_id: int | None = None) -> dict[str, Any]:
    return db_get_quality_metrics(doc_id=doc_id)


@app.get("/metrics/corrections")
def correction_events(doc_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    return db_get_correction_events(doc_id=doc_id, limit=limit)


@app.get("/export/excel")
def export_excel(
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
) -> StreamingResponse:
    """Export confirmed records as the standard admissions master workbook."""
    import io

    rows = get_records(university=university, year=year, faculty=faculty, limit=10000, offset=0)
    if not rows:
        raise HTTPException(status_code=404, detail="No records found for the given filters")
    try:
        content, _count = export_excel_bytes_from_records(rows)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    filename = "admissions_master.xlsx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


assets_dir = FRONTEND_DIST_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
