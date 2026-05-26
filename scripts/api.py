from __future__ import annotations

import json
import os
import sys
import uuid
import csv
import io
from pathlib import Path
from typing import Any

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.agent_workflow import AgentRequest, run_agent_workflow  # noqa: E402
from scripts import fetch_pdfs as fetch_pdfs  # noqa: E402
from scripts import full_vision_extractor as full_vision_extractor  # noqa: E402
from scripts.check_source_updates import check_watchlist_sources  # noqa: E402
from scripts.db import (  # noqa: E402
    confirm_all_by_doc,
    create_consultation_booking,
    create_app_session,
    create_document_submission,
    create_source_document,
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
    get_export_options,
    get_export_records,
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
    list_consultation_bookings,
    list_document_submissions,
    log_api_usage,
    mark_api_key_used,
    recommend_public_programs,
    update_consultation_booking,
    update_document_submission,
    update_staging_record,
)
from scripts.export_excel import export_confirmed_excel_bytes_from_records  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.quality_overview import build_quality_overview  # noqa: E402
from scripts.runtime_paths import ensure_runtime_dirs, frontend_dist_dir, rendered_pages_dir, uploads_dir  # noqa: E402
from scripts.source_change_report import build_change_report, format_markdown_report, load_review_queue  # noqa: E402
from scripts.source_review_state import accept_source_review_receipt, update_source_review_state  # noqa: E402
from scripts.source_watchlist import build_watchlist_report  # noqa: E402
from scripts.validator import validate  # noqa: E402

ensure_runtime_dirs()
INPUT_DIR = uploads_dir()
INPUT_DIR.mkdir(parents=True, exist_ok=True)
FRONTEND_DIST_DIR = frontend_dist_dir()

EXPORT_REQUIRED_COLUMNS = {
    "application_period": "application_period",
    "eju_japanese": "eju_japanese",
    "english_requirement": "english_requirement",
    "screening_schedule": "screening_schedule",
    "result_date": "result_date",
}

OWNER_ISSUE_FIELD_LABELS = {
    "application_period": "申请时间",
    "deadline_rule": "截止规则",
    "eju_session": "EJU 可用考试",
    "eju_japanese": "EJU 日本语",
    "eju_general": "EJU 综合科目",
    "eju_math": "EJU 数学",
    "eju_physics": "EJU 物理",
    "eju_chemistry": "EJU 化学",
    "eju_biology": "EJU 生物",
    "jlpt_requirement": "JLPT",
    "english_requirement": "英语要求",
    "screening_method": "选考方式",
    "screening_schedule": "考试时间",
    "result_date": "结果公布",
    "enrollment_period": "入学手续",
    "required_documents": "所需材料",
    "eligibility": "出愿资格",
    "evidence": "来源依据",
}


def _cors_origins() -> list[str]:
    raw = os.environ.get("CORS_ORIGINS", "")
    origins = {
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:5174",
        "http://127.0.0.1:5174",
        "http://localhost:5175",
        "http://127.0.0.1:5175",
        "http://localhost:5176",
        "http://127.0.0.1:5176",
        "http://localhost:5177",
        "http://127.0.0.1:5177",
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


class AdminBookingUpdateRequest(BaseModel):
    status: str | None = None
    owner_note: str | None = None
    next_action_at: str | None = None


class SourceReviewStateRequest(BaseModel):
    review_status: str = Field(..., min_length=1)
    note: str = ""


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


def _split_filter(value: str | None) -> list[str]:
    if not value:
        return []
    return [part.strip() for part in str(value).replace("，", ",").split(",") if part.strip()]


def _split_int_filter(value: str | None) -> list[int]:
    ids: list[int] = []
    for part in _split_filter(value):
        try:
            next_id = int(part)
        except ValueError:
            continue
        if next_id > 0:
            ids.append(next_id)
    return ids


def _export_rows(
    *,
    university: str | None = None,
    year: int | str | None = None,
    faculty: str | None = None,
    universities: str | None = None,
    years: str | None = None,
    faculties: str | None = None,
    record_ids: str | None = None,
    limit: int = 10000,
    offset: int = 0,
) -> list[dict[str, Any]]:
    university_values = _split_filter(universities) or _split_filter(university)
    year_values = _split_filter(years) or ([str(year)] if year not in ("", None) else [])
    faculty_values = _split_filter(faculties) or _split_filter(faculty)
    id_values = _split_int_filter(record_ids)
    return get_export_records(
        universities=university_values,
        years=year_values,
        faculties=faculty_values,
        record_ids=id_values,
        limit=limit,
        offset=offset,
    )


def _export_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    universities = {str(row.get("university") or "").strip() for row in rows if str(row.get("university") or "").strip()}
    years = {str(row.get("admission_year") or "").strip() for row in rows if str(row.get("admission_year") or "").strip()}
    faculties = {str(row.get("faculty") or "").strip() for row in rows if str(row.get("faculty") or "").strip()}
    missing_required = {
        key: sum(1 for row in rows if key in _export_missing_required(row))
        for key in EXPORT_REQUIRED_COLUMNS
    }
    return {
        "records": len(rows),
        "universities": len(universities),
        "years": sorted(years, reverse=True),
        "faculties": len(faculties),
        "missing_required": missing_required,
        "ready_for_export": bool(rows) and all(count == 0 for count in missing_required.values()),
    }


def _export_missing_required(row: dict[str, Any]) -> list[str]:
    return [
        key
        for key, column in EXPORT_REQUIRED_COLUMNS.items()
        if not str(row.get(column) or "").strip()
    ]


def _export_preview_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [{**row, "export_missing": _export_missing_required(row)} for row in rows]


def _export_review_targets(rows: list[dict[str, Any]], *, limit: int = 50) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for row in rows:
        university = str(row.get("university") or "").strip()
        year = str(row.get("admission_year") or "").strip()
        key = (university, year)
        if not university or key in seen:
            continue
        seen.add(key)
        docs = db_get_documents(query=university, year=year or None, limit=10, offset=0)
        doc = next((item for item in docs if int(item.get("confirmed_count") or 0) > 0 or int(item.get("staging_count") or 0) > 0), None)
        if not doc and docs:
            doc = docs[0]
        if doc:
            targets.append(
                {
                    "university": university,
                    "admission_year": year,
                    "doc_id": doc.get("doc_id"),
                    "filename": doc.get("filename") or "",
                    "source_url": doc.get("source_url") or "",
                    "staging_count": int(doc.get("staging_count") or 0),
                    "confirmed_count": int(doc.get("confirmed_count") or 0),
                }
            )
        if len(targets) >= limit:
            break
    return targets


def _owner_issue_field_label(field: str) -> str:
    return OWNER_ISSUE_FIELD_LABELS.get(field, field)


def _owner_review_target_map(rows: list[dict[str, Any]]) -> dict[tuple[str, str], dict[str, Any]]:
    targets = _export_review_targets(rows, limit=500)
    return {
        (str(item.get("university") or ""), str(item.get("admission_year") or "")): item
        for item in targets
    }


def _export_gap_owner_issues(rows: list[dict[str, Any]], *, limit: int = 30) -> list[dict[str, Any]]:
    target_map = _owner_review_target_map(rows)
    issues: list[dict[str, Any]] = []
    for row in rows:
        missing = _export_missing_required(row)
        if not missing:
            continue
        university = str(row.get("university") or "").strip()
        year = str(row.get("admission_year") or "").strip()
        target = target_map.get((university, year), {})
        for field in missing:
            issues.append(
                {
                    "kind": "export_gap",
                    "priority": 95,
                    "title": f"{university or '未命名学校'}缺少{_owner_issue_field_label(field)}",
                    "university": university,
                    "admission_year": year,
                    "faculty": str(row.get("faculty") or ""),
                    "department": str(row.get("department") or ""),
                    "field": field,
                    "field_label": _owner_issue_field_label(field),
                    "record_id": row.get("id"),
                    "doc_id": target.get("doc_id"),
                    "source_document": target.get("filename") or "",
                    "source_url": target.get("source_url") or row.get("pdf_url") or "",
                    "suggested_action": "进入复审页，对照源 PDF 补齐这项内容后再导出。",
                }
            )
            if len(issues) >= limit:
                return issues
    return issues


def _source_review_owner_issues(*, limit: int = 20) -> list[dict[str, Any]]:
    report = build_change_report(load_review_queue())
    issues: list[dict[str, Any]] = []
    for item in report.get("items") or []:
        if not isinstance(item, dict):
            continue
        review_status = str(item.get("review_status") or "open")
        if review_status in {"reviewed", "deferred"}:
            continue
        status = str(item.get("status") or "")
        priority = 90 if status == "changed" else 85 if status in {"failed", "marker_mismatch"} else 75
        issues.append(
            {
                "kind": "source_change",
                "priority": priority,
                "title": item.get("owner_summary") or item.get("status_label") or "官方来源需要查看",
                "university": str(item.get("university") or ""),
                "admission_year": str(item.get("admission_year") or ""),
                "field": "",
                "field_label": "",
                "source_document": str(item.get("stem") or ""),
                "source_url": str(item.get("source_url") or ""),
                "review_item_id": str(item.get("item_id") or ""),
                "suggested_action": item.get("recommended_action") or "先确认官方来源变化，再决定是否重新整理。",
            }
        )
        if len(issues) >= limit:
            break
    return issues


def _baseline_owner_issues(overview: dict[str, Any], *, limit: int = 20) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    for todo in overview.get("quality_todo") or []:
        if not isinstance(todo, dict):
            continue
        field = str(todo.get("field") or "")
        seed = str(todo.get("seed") or "")
        issues.append(
            {
                "kind": "baseline_gap",
                "priority": int(todo.get("priority") or 40),
                "title": f"基准覆盖还需要补看：{_owner_issue_field_label(field) if field else seed}",
                "university": "",
                "admission_year": "",
                "field": field,
                "field_label": _owner_issue_field_label(field) if field else "",
                "source_document": seed,
                "source_url": "",
                "checked": todo.get("checked"),
                "minimum": todo.get("minimum"),
                "suggested_action": str(todo.get("details") or "补充人工确认过的基准样本。"),
            }
        )
        if len(issues) >= limit:
            break
    return issues


def _manual_correction_owner_issues(*, limit: int = 20) -> list[dict[str, Any]]:
    corrections = db_get_correction_events(limit=200)
    grouped: dict[tuple[str, str, str], dict[str, Any]] = {}
    for item in corrections:
        key = (
            str(item.get("university") or ""),
            str(item.get("admission_year") or ""),
            str(item.get("field_name") or ""),
        )
        current = grouped.setdefault(
            key,
            {
                "kind": "manual_correction",
                "priority": 60,
                "title": "",
                "university": key[0],
                "admission_year": key[1],
                "field": key[2],
                "field_label": _owner_issue_field_label(key[2]),
                "source_document": "",
                "source_url": "",
                "count": 0,
                "latest_at": "",
                "suggested_action": "这项最近被人工改过，优先回看抽取规则或基准样本，避免同类资料反复手修。",
            },
        )
        current["count"] = int(current.get("count") or 0) + 1
        current["latest_at"] = max(str(current.get("latest_at") or ""), str(item.get("created_at") or ""))
        current["document_id"] = item.get("document_id")
    issues = list(grouped.values())
    for issue in issues:
        issue["title"] = f"{issue.get('university') or '未命名学校'}的{issue.get('field_label') or issue.get('field')}被人工修改 {issue.get('count')} 次"
    return sorted(issues, key=lambda item: (-int(item.get("count") or 0), str(item.get("university") or "")))[:limit]


def _owner_top_issues(*, limit: int = 20) -> dict[str, Any]:
    export_rows = _export_rows(limit=10000, offset=0)
    overview = build_quality_overview(include_source_text_health=False)
    issues = (
        _export_gap_owner_issues(export_rows)
        + _source_review_owner_issues()
        + _baseline_owner_issues(overview)
        + _manual_correction_owner_issues()
    )
    issues = sorted(
        issues,
        key=lambda item: (
            -int(item.get("priority") or 0),
            str(item.get("university") or ""),
            str(item.get("admission_year") or ""),
            str(item.get("field") or ""),
        ),
    )[: max(1, min(int(limit or 20), 100))]
    summary: dict[str, int] = {}
    for item in issues:
        kind = str(item.get("kind") or "other")
        summary[kind] = summary.get(kind, 0) + 1
    return {
        "summary": {
            "total": len(issues),
            "by_kind": summary,
            "export_ready": _export_summary(export_rows)["ready_for_export"],
            "quality_status": overview.get("overall_status", ""),
        },
        "issues": issues,
    }


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


@app.get("/admin/bookings")
def admin_bookings(
    request: Request,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    _require_owner(request)
    return list_consultation_bookings(status=status, q=q, limit=limit, offset=offset)


@app.get("/admin/bookings/export.csv")
def admin_bookings_export_csv(
    request: Request,
    status: str | None = None,
    q: str | None = None,
) -> StreamingResponse:
    _require_owner(request)
    rows = list_consultation_bookings(status=status, q=q, limit=10000, offset=0)
    buffer = io.StringIO()
    fieldnames = [
        "状态",
        "学生姓名",
        "联系方式",
        "身份",
        "目标年度",
        "目标学校",
        "学部",
        "学科",
        "方便时间",
        "想咨询的问题",
        "跟进备注",
        "下次跟进",
        "提交时间",
    ]
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                "状态": row.get("status") or "",
                "学生姓名": row.get("student_name") or "",
                "联系方式": row.get("contact_email") or row.get("contact_phone") or "",
                "身份": row.get("role") or "",
                "目标年度": row.get("target_year") or row.get("admission_year") or "",
                "目标学校": row.get("school_name") or "",
                "学部": row.get("faculty") or "",
                "学科": row.get("department") or "",
                "方便时间": row.get("preferred_times") or "",
                "想咨询的问题": row.get("question") or "",
                "跟进备注": row.get("owner_note") or "",
                "下次跟进": row.get("next_action_at") or "",
                "提交时间": row.get("created_at") or "",
            }
        )
    return StreamingResponse(
        iter(["\ufeff" + buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="consultation_bookings.csv"'},
    )


@app.patch("/admin/bookings/{booking_id}")
def admin_update_booking(booking_id: int, payload: AdminBookingUpdateRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    allowed = {"new", "contacted", "done", "closed"}
    if payload.status is not None and payload.status not in allowed:
        raise HTTPException(status_code=400, detail="booking status is not supported")
    updated = update_consultation_booking(
        booking_id,
        status=payload.status,
        owner_note=payload.owner_note,
        next_action_at=payload.next_action_at,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="booking not found")
    return updated


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
    if os.environ.get("ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW") == "1":
        doc_id = create_source_document(
            request.university,
            "browser-smoke.pdf",
            "",
            request.pdf_url,
            request.year,
        )
        insert_staging_record(
            doc_id,
            1,
            validate(
                {
                    "university": request.university,
                    "admission_year": request.year,
                    "admission_period": "2027年4月入学",
                    "faculty": "ブラウザテスト学部",
                    "department": "留学生入試",
                    "application_period": "2026年9月1日 - 2026年9月10日",
                    "deadline_rule": "最終日必着",
                    "eju_session": "2025年度または2026年度",
                    "eju_japanese": "日本語を利用",
                    "english_requirement": "要項確認",
                    "screening_method": "書類審査・面接",
                    "screening_schedule": "2026年10月",
                    "result_date": "2026年11月",
                    "enrollment_period": "2027年3月",
                    "prefecture": "東京",
                    "campus": "テストキャンパス",
                    "confidence": 0.82,
                    "needs_review": 1,
                    "risk_level": "medium",
                    "warnings_json": ["browser smoke seeded record"],
                }
            ),
        )
        updated = update_document_submission(
            submission_id,
            processing_status="needs_owner_review",
            document_id=doc_id,
        )
        if not updated:
            raise HTTPException(status_code=404, detail="submission not found")
        updated["workflow_status"] = "browser_smoke_completed"
        updated["records"] = 0
        return updated
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


async def _submission_payload_from_request(request: Request) -> dict[str, Any]:
    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" not in content_type:
        try:
            data = await request.json()
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

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
    return data


@app.post("/partner/submissions")
async def partner_create_submission(request: Request) -> dict[str, Any]:
    user = _require_user(request, {"partner_staff"})
    data = await _submission_payload_from_request(request)
    if not str(data.get("university") or "").strip():
        raise HTTPException(status_code=400, detail="请填写学校名称")
    if not any(str(data.get(field) or "").strip() for field in ("pdf_url", "page_url", "file_name")):
        raise HTTPException(status_code=400, detail="请上传 PDF，或填写 PDF 地址/官网页面")
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


@app.get("/metrics/quality-overview")
def quality_overview(request: Request) -> dict[str, Any]:
    _require_owner(request)
    overview = build_quality_overview(include_source_text_health=False)
    source_watchlist = overview.get("source_watchlist") if isinstance(overview.get("source_watchlist"), dict) else {}
    source_review_queue = overview.get("source_review_queue") if isinstance(overview.get("source_review_queue"), dict) else {}
    return {
        "overall_status": overview.get("overall_status", ""),
        "language_requirement_coverage": overview.get("language_requirement_coverage", {}),
        "per_seed_thin_coverage": overview.get("per_seed_thin_coverage", []),
        "source_watchlist_summary": source_watchlist.get("summary", {}),
        "source_review_summary": source_review_queue.get("summary", {}),
        "quality_todo": overview.get("quality_todo", []),
        "next_owner_action": overview.get("next_owner_action"),
    }


@app.get("/metrics/owner-issues")
def owner_top_issues(request: Request, limit: int = 20) -> dict[str, Any]:
    _require_owner(request)
    return _owner_top_issues(limit=limit)


@app.get("/metrics/corrections")
def correction_events(request: Request, doc_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    _require_owner(request)
    return db_get_correction_events(doc_id=doc_id, limit=limit)


@app.get("/admin/source-review-queue")
def source_review_queue(request: Request) -> dict[str, Any]:
    _require_owner(request)
    return build_change_report(load_review_queue())


@app.get("/admin/source-review-report.md")
def source_review_report_markdown(request: Request) -> Response:
    _require_owner(request)
    report = build_change_report(load_review_queue())
    markdown = format_markdown_report(report)
    return Response(
        content=markdown,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="source-review-report.md"'},
    )


@app.get("/admin/source-watchlist")
def source_watchlist(request: Request) -> dict[str, Any]:
    _require_owner(request)
    return build_watchlist_report()


@app.patch("/admin/source-review-queue/{item_id}")
def update_source_review_queue_item(item_id: str, payload: SourceReviewStateRequest, request: Request) -> dict[str, Any]:
    _require_owner(request)
    try:
        state = update_source_review_state(item_id, payload.review_status, note=payload.note)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return state


@app.post("/admin/source-review-queue/{item_id}/accept-source")
def accept_source_review_queue_item(item_id: str, request: Request) -> dict[str, Any]:
    _require_owner(request)
    report = build_change_report(load_review_queue())
    item = next((entry for entry in report.get("items", []) if entry.get("item_id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="source review item not found")
    try:
        receipt = accept_source_review_receipt(item)
        state = update_source_review_state(item_id, "reviewed", note="已接受新的官方来源凭证")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {
        "status": "accepted",
        "receipt": receipt,
        "review_state": state,
        "confirmed_records_unchanged": True,
    }


@app.post("/admin/source-review-queue/{item_id}/reextract")
def reextract_source_review_queue_item(item_id: str, request: Request) -> dict[str, Any]:
    _require_owner(request)
    report = build_change_report(load_review_queue())
    item = next((entry for entry in report.get("items", []) if entry.get("item_id") == item_id), None)
    if not item:
        raise HTTPException(status_code=404, detail="source review item not found")
    source_url = str(item.get("source_url") or "").strip()
    if not source_url:
        raise HTTPException(status_code=400, detail="source review item has no source URL")

    source_type = str(item.get("source_type") or "").strip().lower()
    is_pdf = source_type == "pdf" or source_url.lower().split("?", 1)[0].endswith(".pdf")
    workflow_request = AgentRequest(
        pdf_url=source_url if is_pdf else "",
        page_url="" if is_pdf else source_url,
        university=str(item.get("university") or ""),
        year=str(item.get("admission_year") or "2026"),
    )
    try:
        result = run_agent_workflow(workflow_request)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail={"error": "source reextract failed", "message": str(exc)})

    doc_id = int(result.get("doc_id") or 0)
    if doc_id:
        update_source_review_state(item_id, "reviewed", note=f"重新整理完成，待复审资料 #{doc_id}")
    else:
        update_source_review_state(item_id, "needs_reextract", note="已尝试重新整理，但仍需要确认来源")
    return {
        "status": result.get("status", "completed"),
        "doc_id": doc_id or None,
        "records": result.get("records", 0),
        "quality_status": result.get("quality_status", "needs_review"),
        "review_required": True,
        "source": result.get("source", {}),
    }


@app.post("/admin/source-checks/run")
def run_source_checks(request: Request, limit: int | None = None) -> dict[str, Any]:
    _require_owner(request)
    report = check_watchlist_sources(limit=limit if limit and limit > 0 else None)
    queue = build_change_report(load_review_queue())
    return {
        "checked_at": report.get("checked_at", ""),
        "summary": report.get("summary", {}),
        "review_queue": queue,
    }


@app.get("/export/excel")
def export_excel(
    request: Request,
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
    universities: str | None = None,
    years: str | None = None,
    faculties: str | None = None,
    record_ids: str | None = None,
) -> StreamingResponse:
    """Export confirmed records as the standard admissions master workbook."""
    _require_owner(request)

    rows = _export_rows(
        university=university,
        year=year,
        faculty=faculty,
        universities=universities,
        years=years,
        faculties=faculties,
        record_ids=record_ids,
        limit=10000,
        offset=0,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No records found for the given filters")
    try:
        content, _count = export_confirmed_excel_bytes_from_records(rows)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    filename = "admissions_master.xlsx"
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/export/csv")
def export_csv(
    request: Request,
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
    universities: str | None = None,
    years: str | None = None,
    faculties: str | None = None,
    record_ids: str | None = None,
) -> StreamingResponse:
    _require_owner(request)
    rows = _export_rows(
        university=university,
        year=year,
        faculty=faculty,
        universities=universities,
        years=years,
        faculties=faculties,
        record_ids=record_ids,
        limit=10000,
        offset=0,
    )
    if not rows:
        raise HTTPException(status_code=404, detail="No records found for the given filters")
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="admissions_export.csv"'},
    )


@app.get("/exports/preview")
def export_preview(
    request: Request,
    university: str | None = None,
    year: int | None = None,
    faculty: str | None = None,
    universities: str | None = None,
    years: str | None = None,
    faculties: str | None = None,
    record_ids: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> dict[str, Any]:
    _require_owner(request)
    rows = _export_rows(
        university=university,
        year=year,
        faculty=faculty,
        universities=universities,
        years=years,
        faculties=faculties,
        record_ids=record_ids,
        limit=max(1, min(int(limit), 1000)),
        offset=max(0, int(offset)),
    )
    return {
        "summary": _export_summary(rows),
        "review_targets": _export_review_targets(rows),
        "rows": _export_preview_rows(rows),
    }


@app.get("/exports/options")
def export_options(request: Request, limit: int = 200) -> dict[str, Any]:
    _require_owner(request)
    return get_export_options(limit=max(1, min(int(limit), 500)))


assets_dir = FRONTEND_DIST_DIR / "assets"
if assets_dir.exists():
    app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")
