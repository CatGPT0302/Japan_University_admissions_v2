from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.agent_workflow import AgentRequest, run_agent_workflow  # noqa: E402
from scripts import fetch_pdfs as fetch_pdfs  # noqa: E402
from scripts import full_vision_extractor as full_vision_extractor  # noqa: E402
from scripts.db import (  # noqa: E402
    confirm_all_by_doc,
    create_consultation_booking,
    create_app_session,
    create_document_submission,
    delete_app_session,
    delete_document,
    delete_staging_record,
    get_api_center,
    get_app_user_by_session,
    get_api_key_context,
    get_correction_events as db_get_correction_events,
    get_db_runtime,
    get_document_submission,
    get_document_file as db_get_document_file,
    get_documents as db_get_documents,
    get_document_summary as db_get_document_summary,
    get_document_submission_for_owner,
    get_public_program,
    get_public_programs,
    get_quality_metrics as db_get_quality_metrics,
    get_records,
    get_stats as db_get_stats,
    get_staging_record,
    get_staging_records,
    init_db,
    insert_staging_record,
    issue_api_key,
    list_document_submissions,
    log_api_usage,
    mark_api_key_used,
    recommend_public_programs,
    update_document_submission,
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


class AgentRunRequest(BaseModel):
    file_name: str | None = ""
    pdf_url: str | None = ""
    page_url: str | None = ""
    university: str | None = ""
    year: str


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


class StudentProfile(BaseModel):
    target_year: str | None = ""
    desired_fields: list[str] = Field(default_factory=list)
    preferred_prefectures: list[str] = Field(default_factory=list)
    english_tests: list[str] = Field(default_factory=list)
    eju_subjects: list[str] = Field(default_factory=list)
    japanese_level: str | None = ""
    notes: str | None = ""


class ConsultationBookingRequest(BaseModel):
    student_name: str
    contact_email: str | None = ""
    contact_phone: str | None = ""
    role: str | None = ""
    target_year: str | None = ""
    program_id: int | None = None
    preferred_times: str | None = ""
    question: str | None = ""


class ApiKeyCreateRequest(BaseModel):
    client_name: str = "Main integration"


class LicensedDocumentSubmissionRequest(BaseModel):
    university: str
    admission_year: str | None = ""
    pdf_url: str | None = ""
    page_url: str | None = ""
    file_name: str | None = ""
    original_file_name: str | None = ""
    notes: str | None = ""


class AdminSubmissionUpdateRequest(BaseModel):
    processing_status: str | None = None
    document_id: int | None = None


class LoginRequest(BaseModel):
    email: str
    password: str


class PartnerSubmissionRequest(BaseModel):
    university: str
    admission_year: str | None = ""
    pdf_url: str | None = ""
    page_url: str | None = ""
    notes: str | None = ""


def _model_data(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _session_token(request: Request) -> str:
    return request.cookies.get("admissions_session", "").strip()


def _current_user(request: Request) -> dict[str, Any] | None:
    return get_app_user_by_session(_session_token(request))


def _require_user(request: Request, roles: set[str] | None = None) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Please sign in")
    if roles and user.get("role") not in roles:
        raise HTTPException(status_code=403, detail="This area is not available for this account")
    return user


def _require_owner(request: Request) -> dict[str, Any]:
    return _require_user(request, {"owner_admin"})


def _extract_api_secret(request: Request) -> str:
    auth = request.headers.get("authorization", "").strip()
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.headers.get("x-api-key", "").strip()


def _licensed_context(request: Request, scope: str) -> dict[str, Any]:
    secret = _extract_api_secret(request)
    if not secret:
        log_api_usage(None, None, request.method, request.url.path, scope, 401)
        raise HTTPException(status_code=401, detail="API key required")
    context = get_api_key_context(secret)
    if not context:
        log_api_usage(None, None, request.method, request.url.path, scope, 401)
        raise HTTPException(status_code=401, detail="Invalid API key")
    org_id = int(context.get("organization_id") or 0)
    key_id = int(context.get("api_key_id") or 0)
    if context.get("key_status") != "active" or context.get("organization_status") != "active" or context.get("client_status") != "active":
        log_api_usage(org_id, key_id, request.method, request.url.path, scope, 401)
        raise HTTPException(status_code=401, detail="API key is not active")
    if scope not in set(context.get("scopes") or []):
        log_api_usage(org_id, key_id, request.method, request.url.path, scope, 403)
        raise HTTPException(status_code=403, detail=f"Missing API scope: {scope}")
    mark_api_key_used(key_id)
    return context


def _log_success(request: Request, context: dict[str, Any], scope: str) -> None:
    log_api_usage(
        int(context.get("organization_id") or 0),
        int(context.get("api_key_id") or 0),
        request.method,
        request.url.path,
        scope,
        200,
    )


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
async def upload_pdf(request: Request, file: UploadFile = File(...)) -> dict[str, str]:
    _require_owner(request)
    suffix = Path(file.filename or "").suffix or ".pdf"
    original_name = Path(file.filename or "uploaded.pdf").name
    stem = Path(original_name).stem or "uploaded"
    saved_name = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
    save_path = INPUT_DIR / saved_name
    content = await file.read()
    save_path.write_bytes(content)
    return {
        "file_name": saved_name,
        "original_file_name": original_name,
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


@app.post("/auth/login")
def login(payload: LoginRequest) -> JSONResponse:
    session = create_app_session(payload.email, payload.password)
    if not session:
        raise HTTPException(status_code=401, detail="Email or password is not correct")
    token, user = session
    response = JSONResponse({"user": user})
    response.set_cookie(
        "admissions_session",
        token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=60 * 60 * 24 * 7,
        path="/",
    )
    return response


@app.post("/auth/logout")
def logout(request: Request) -> JSONResponse:
    delete_app_session(_session_token(request))
    response = JSONResponse({"status": "signed_out"})
    response.delete_cookie("admissions_session", path="/")
    return response


@app.get("/auth/me")
def auth_me(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    return {"user": user}


@app.post("/extract")
def extract_pdf(payload: ExtractRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
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
def extract_pdf_full_vision(payload: ExtractRequest, request: Request) -> dict[str, Any]:
    return extract_pdf(payload, request)


@app.post("/agent/run")
def run_agent(payload: AgentRunRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    try:
        return run_agent_workflow(
            AgentRequest(
                file_name=payload.file_name or "",
                pdf_url=payload.pdf_url or "",
                page_url=payload.page_url or "",
                university=payload.university or "",
                year=payload.year,
            )
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "error": "agent_workflow failed",
                "message": str(exc),
            },
        )


@app.get("/fetch-pdf/targets")
def fetch_pdf_targets(request: Request) -> list[dict[str, str]]:
    _require_owner(request)
    return fetch_pdfs.list_targets()


@app.post("/fetch-pdf/search")
def search_pdf(payload: SearchPdfRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
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
def probe_pdf_sources(request: Request, year: int = 2026) -> dict[str, Any]:
    _require_owner(request)
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
def fetch_pdf(payload: FetchPdfRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
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
    request: Request,
    q: str | None = None,
    year: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _require_owner(request)
    return db_get_documents(query=q, year=year, limit=limit, offset=offset)


@app.get("/documents/{doc_id}/summary")
def get_document_summary(doc_id: int, request: Request) -> dict[str, Any]:
    _require_owner(request)
    row = db_get_document_summary(doc_id)
    if not row:
        raise HTTPException(status_code=404, detail="document not found")
    return row


@app.get("/documents/{doc_id}/pdf")
def get_document_pdf(doc_id: int, request: Request) -> FileResponse:
    _require_owner(request)
    pdf_path = _document_pdf_path(doc_id)
    return FileResponse(
        pdf_path,
        media_type="application/pdf",
        headers={"Content-Disposition": "inline"},
    )


@app.get("/documents/{doc_id}/page-image")
def get_document_page_image(doc_id: int, request: Request, page: int = 1) -> FileResponse:
    _require_owner(request)
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
def delete_uploaded_document(doc_id: int, request: Request) -> dict[str, Any]:
    _require_owner(request)
    result = delete_document(doc_id)
    if not result:
        raise HTTPException(status_code=404, detail="document not found")
    return {"status": "deleted", **result}


@app.get("/staging/{doc_id}")
def list_staging(doc_id: int, request: Request) -> list[dict[str, Any]]:
    _require_owner(request)
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
def patch_staging(staging_id: int, payload: PatchRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    updated = update_staging_record(staging_id, payload.data)
    if not updated:
        raise HTTPException(status_code=404, detail=f"staging record not found: {staging_id}")
    return updated


@app.delete("/staging/{staging_id}")
def delete_staging(staging_id: int, request: Request) -> dict[str, Any]:
    _require_owner(request)
    row = get_staging_record(staging_id)
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    delete_staging_record(staging_id)
    return {"status": "deleted", "id": staging_id}


@app.post("/staging/manual")
def create_manual_staging(payload: ManualRecord, request: Request) -> dict[str, Any]:
    _require_owner(request)
    record = dict(payload.data or {})
    validated = validate(record)
    row_id = insert_staging_record(payload.document_id, None, validated)
    return {"id": row_id, "status": "created"}


@app.post("/confirm/{doc_id}")
def confirm_doc(doc_id: int, request: Request) -> dict[str, int]:
    _require_owner(request)
    stats = confirm_all_by_doc(doc_id)
    return {
        "confirmed": int(stats.get("written", 0)),
        "skipped": int(stats.get("skipped", 0)),
    }


@app.get("/records")
def list_records(
    request: Request,
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _require_owner(request)
    rows = get_records(
        university=university,
        year=year,
        faculty=faculty,
        limit=limit,
        offset=offset,
    )
    return rows


@app.get("/public/programs")
def public_programs(
    university: str | None = None,
    year: str | None = None,
    faculty: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    return get_public_programs(university=university, year=year, faculty=faculty, limit=limit, offset=offset)


@app.get("/public/programs/{program_id}")
def public_program_detail(program_id: int) -> dict[str, Any]:
    program = get_public_program(program_id)
    if not program:
        raise HTTPException(status_code=404, detail="program not found")
    return program


@app.post("/public/recommendations")
def public_recommendations(profile: StudentProfile) -> dict[str, Any]:
    return recommend_public_programs(_model_data(profile))


@app.post("/public/bookings")
def public_booking(payload: ConsultationBookingRequest) -> dict[str, Any]:
    data = _model_data(payload)
    if not str(data.get("student_name") or "").strip():
        raise HTTPException(status_code=400, detail="student_name is required")
    if not str(data.get("contact_email") or "").strip() and not str(data.get("contact_phone") or "").strip():
        raise HTTPException(status_code=400, detail="contact_email or contact_phone is required")
    data["status"] = "new"
    booking_id = create_consultation_booking(data)
    return {"status": "received", "id": booking_id}


@app.get("/settings/api-center")
def settings_api_center(request: Request) -> dict[str, Any]:
    user = _require_user(request, {"owner_admin", "partner_staff"})
    if user.get("role") == "partner_staff":
        return get_api_center(int(user.get("organization_id") or 0))
    return get_api_center()


@app.post("/settings/api-keys")
def settings_create_api_key(payload: ApiKeyCreateRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    center = get_api_center()
    organization_name = (center.get("organization") or {}).get("name") or "Owner Workspace"
    created = issue_api_key(organization_name=organization_name, client_name=payload.client_name)
    return {
        "key_id": created["key_id"],
        "secret": created["secret"],
        "masked_key": created["masked_key"],
        "scopes": created["scopes"],
    }


@app.get("/admin/submissions")
def admin_submission_queue(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _require_owner(request)
    return list_document_submissions(status=status, limit=limit, offset=offset)


@app.patch("/admin/submissions/{submission_id}")
def admin_update_submission(submission_id: int, payload: AdminSubmissionUpdateRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    try:
        updated = update_document_submission(
            submission_id,
            processing_status=payload.processing_status,
            document_id=payload.document_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    if not updated:
        raise HTTPException(status_code=404, detail="submission not found")
    return updated


@app.post("/admin/submissions/{submission_id}/start")
def admin_start_submission(submission_id: int, request: Request) -> dict[str, Any]:
    _require_owner(request)
    submission = get_document_submission_for_owner(submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="submission not found")
    if not any(str(submission.get(field) or "").strip() for field in ("file_name", "pdf_url", "page_url")):
        raise HTTPException(status_code=400, detail="submission needs a PDF, PDF URL, or page URL")

    update_document_submission(submission_id, processing_status="processing")
    request = AgentRequest(
        file_name=str(submission.get("file_name") or ""),
        pdf_url=str(submission.get("pdf_url") or ""),
        page_url=str(submission.get("page_url") or ""),
        university=str(submission.get("university") or ""),
        year=str(submission.get("admission_year") or ""),
    )
    try:
        result = run_agent_workflow(request)
    except FileNotFoundError as exc:
        update_document_submission(submission_id, processing_status="needs_more_info")
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        update_document_submission(submission_id, processing_status="needs_more_info")
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        update_document_submission(submission_id, processing_status="failed")
        raise HTTPException(status_code=500, detail={"error": "submission processing failed", "message": str(exc)})

    next_status = "needs_owner_review" if result.get("doc_id") else "needs_more_info"
    updated = update_document_submission(
        submission_id,
        processing_status=next_status,
        document_id=int(result.get("doc_id") or 0) if result.get("doc_id") else None,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="submission not found")
    updated["workflow_status"] = result.get("status", "")
    updated["records"] = result.get("records", 0)
    return updated


@app.get("/v1/programs")
def licensed_programs(
    request: Request,
    university: str | None = None,
    year: str | None = None,
    faculty: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    context = _licensed_context(request, "programs:read")
    data = get_public_programs(university=university, year=year, faculty=faculty, limit=limit, offset=offset)
    _log_success(request, context, "programs:read")
    return data


@app.get("/v1/programs/{program_id}")
def licensed_program_detail(program_id: int, request: Request) -> dict[str, Any]:
    context = _licensed_context(request, "programs:read")
    program = get_public_program(program_id)
    if not program:
        log_api_usage(
            int(context.get("organization_id") or 0),
            int(context.get("api_key_id") or 0),
            request.method,
            request.url.path,
            "programs:read",
            404,
        )
        raise HTTPException(status_code=404, detail="Program not found")
    _log_success(request, context, "programs:read")
    return program


@app.post("/v1/recommendations")
def licensed_recommendations(profile: StudentProfile, request: Request) -> dict[str, Any]:
    context = _licensed_context(request, "recommendations:create")
    data = recommend_public_programs(_model_data(profile))
    _log_success(request, context, "recommendations:create")
    return data


@app.post("/v1/bookings")
def licensed_booking(payload: ConsultationBookingRequest, request: Request) -> dict[str, Any]:
    context = _licensed_context(request, "bookings:create")
    if not (payload.contact_email or payload.contact_phone):
        log_api_usage(
            int(context.get("organization_id") or 0),
            int(context.get("api_key_id") or 0),
            request.method,
            request.url.path,
            "bookings:create",
            400,
        )
        raise HTTPException(status_code=400, detail="Contact email or phone is required")
    data = _model_data(payload)
    data["status"] = "new"
    booking_id = create_consultation_booking(data)
    _log_success(request, context, "bookings:create")
    return {"status": "received", "id": booking_id}


@app.post("/v1/documents/submissions")
async def licensed_document_submission(request: Request) -> dict[str, Any]:
    context = _licensed_context(request, "documents:submit")
    content_type = request.headers.get("content-type", "")
    data: dict[str, Any]
    if "multipart/form-data" in content_type:
        form = await request.form()
        data = {
            "university": str(form.get("university") or ""),
            "admission_year": str(form.get("admission_year") or ""),
            "pdf_url": str(form.get("pdf_url") or ""),
            "page_url": str(form.get("page_url") or ""),
            "notes": str(form.get("notes") or ""),
            "file_name": "",
            "original_file_name": "",
        }
        file = form.get("file")
        if file is not None and hasattr(file, "filename") and hasattr(file, "read"):
            original_name = Path(getattr(file, "filename", "") or "submitted.pdf").name
            suffix = Path(original_name).suffix or ".pdf"
            stem = Path(original_name).stem or "submitted"
            saved_name = f"{stem}-{uuid.uuid4().hex[:8]}{suffix}"
            save_path = INPUT_DIR / saved_name
            save_path.write_bytes(await file.read())
            data["file_name"] = saved_name
            data["original_file_name"] = original_name
    else:
        try:
            data = await request.json()
        except Exception:
            data = {}
    if not str(data.get("university") or "").strip():
        raise HTTPException(status_code=400, detail="University is required")
    if not any(str(data.get(field) or "").strip() for field in ("pdf_url", "page_url", "file_name")):
        raise HTTPException(status_code=400, detail="PDF URL, page URL, or file name is required")
    submission_id = create_document_submission(
        int(context.get("organization_id") or 0),
        int(context.get("api_key_id") or 0),
        data,
    )
    _log_success(request, context, "documents:submit")
    return {"status": "submitted", "id": submission_id, "processing_status": "submitted"}


@app.get("/v1/documents/submissions/{submission_id}")
def licensed_document_submission_detail(submission_id: int, request: Request) -> dict[str, Any]:
    context = _licensed_context(request, "documents:read_status")
    submission = get_document_submission(int(context.get("organization_id") or 0), submission_id)
    if not submission:
        log_api_usage(
            int(context.get("organization_id") or 0),
            int(context.get("api_key_id") or 0),
            request.method,
            request.url.path,
            "documents:read_status",
            404,
        )
        raise HTTPException(status_code=404, detail="Submission not found")
    _log_success(request, context, "documents:read_status")
    return submission


@app.post("/partner/submissions")
async def partner_create_submission(payload: PartnerSubmissionRequest, request: Request) -> dict[str, Any]:
    user = _require_user(request, {"partner_staff"})
    data = _model_data(payload)
    if not str(data.get("university") or "").strip():
        raise HTTPException(status_code=400, detail="请填写学校名称")
    if not any(str(data.get(field) or "").strip() for field in ("pdf_url", "page_url")):
        raise HTTPException(status_code=400, detail="请填写 PDF 地址或官网页面")
    submission_id = create_document_submission(
        int(user.get("organization_id") or 0),
        None,
        data,
    )
    return {"status": "submitted", "id": submission_id, "processing_status": "submitted"}


@app.get("/partner/submissions")
def partner_submissions(
    request: Request,
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    user = _require_user(request, {"partner_staff"})
    return list_document_submissions(
        status=status,
        limit=limit,
        offset=offset,
        organization_id=int(user.get("organization_id") or 0),
    )


@app.get("/stats")
def get_stats(request: Request) -> dict[str, Any]:
    _require_owner(request)
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
def quality_metrics(request: Request, doc_id: int | None = None) -> dict[str, Any]:
    _require_owner(request)
    return db_get_quality_metrics(doc_id=doc_id)


@app.get("/metrics/corrections")
def correction_events(request: Request, doc_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    _require_owner(request)
    return db_get_correction_events(doc_id=doc_id, limit=limit)


@app.get("/export/excel")
def export_excel(
    request: Request,
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
) -> StreamingResponse:
    """Export confirmed records as the standard admissions master workbook."""
    _require_owner(request)
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
