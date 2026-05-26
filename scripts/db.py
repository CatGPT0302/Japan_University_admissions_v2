"""
admissions_v2 database layer.
Supports PostgreSQL in production and SQLite in local development.
"""
from __future__ import annotations

import json
import hashlib
import os
import re
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import quote

from scripts.runtime_paths import sqlite_path
from scripts.validator import normalize_manual_modified_fields, validate

JSON_LIST_FIELDS = {"warnings_json", "manual_modified_fields"}
JSON_DICT_FIELDS = {"field_confidence", "field_evidence", "raw_llm_json"}
STAGING_JSON_FIELDS = JSON_LIST_FIELDS | JSON_DICT_FIELDS
TRACKABLE_FIELDS = {
    "university",
    "application_period",
    "deadline_rule",
    "eju_session",
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
    "english_requirement",
    "screening_method",
    "screening_schedule",
    "result_date",
    "enrollment_period",
    "faculty",
    "department",
    "campus",
    "prefecture",
}
QUALITY_FIELDS = [
    "application_period",
    "deadline_rule",
    "eju_session",
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
    "english_requirement",
    "screening_method",
    "screening_schedule",
    "result_date",
    "enrollment_period",
]


@dataclass(frozen=True)
class DbRuntime:
    mode: str
    url: str
    source: str
    sqlite_path: str
    persistent: bool
    warning: str


def _build_pg_url_from_parts() -> tuple[str, str]:
    host = os.environ.get("PGHOST", "").strip()
    database = os.environ.get("PGDATABASE", "").strip()
    user = os.environ.get("PGUSER", "").strip()
    password = os.environ.get("PGPASSWORD", "")
    port = os.environ.get("PGPORT", "").strip() or "5432"
    if not (host and database and user):
        return "", ""
    auth = quote(user)
    if password:
        auth += f":{quote(password)}"
    return f"postgresql://{auth}@{host}:{port}/{database}", "PG* parts"


def _resolve_database_url() -> tuple[str, str]:
    for name in (
        "DATABASE_URL",
        "DATABASE_PUBLIC_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
        "PGDATABASE_URL",
    ):
        value = os.environ.get(name, "").strip()
        if value.startswith("postgres"):
            return value, name
    return _build_pg_url_from_parts()


def _sqlite_path() -> Path:
    raw = (
        os.environ.get("SQLITE_PATH", "").strip()
        or os.environ.get("SQLITE_DB_PATH", "").strip()
    )
    if raw:
        return Path(raw)
    volume_mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if volume_mount:
        return Path(volume_mount) / "admissions_v2.db"
    return sqlite_path()


DATABASE_URL, DATABASE_URL_SOURCE = _resolve_database_url()
SQLITE_PATH = _sqlite_path()


def get_db_runtime() -> DbRuntime:
    railway = bool(os.environ.get("RAILWAY_ENVIRONMENT_NAME") or os.environ.get("RAILWAY_PROJECT_ID"))
    volume_mount = os.environ.get("RAILWAY_VOLUME_MOUNT_PATH", "").strip()
    if DATABASE_URL and DATABASE_URL.startswith("postgres"):
        return DbRuntime(
            mode="postgres",
            url=DATABASE_URL,
            source=DATABASE_URL_SOURCE or "DATABASE_URL",
            sqlite_path="",
            persistent=True,
            warning="",
        )
    warning = "railway_sqlite_ephemeral" if railway else ""
    persistent = not railway
    if railway and volume_mount and str(SQLITE_PATH).startswith(volume_mount):
        persistent = True
        warning = ""
    return DbRuntime(
        mode="sqlite",
        url="",
        source="sqlite-fallback",
        sqlite_path=str(SQLITE_PATH),
        persistent=persistent,
        warning=warning,
    )


def _pg() -> bool:
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))


def _ph() -> str:
    return "%s" if _pg() else "?"


def _phn(n: int) -> str:
    return ",".join(_ph() for _ in range(n))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def get_conn():
    if _pg():
        import psycopg2
        import psycopg2.extras

        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)

    db_path = SQLITE_PATH
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _fetchall(conn, sql: str, params=()):
    if _pg():
        cur = conn.cursor()
        cur.execute(sql, params)
        return [dict(row) for row in cur.fetchall()]
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def _fetchone(conn, sql: str, params=()):
    if _pg():
        cur = conn.cursor()
        cur.execute(sql, params)
        row = cur.fetchone()
        return dict(row) if row else None
    row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def _execute(conn, sql: str, params=()):
    if _pg():
        cur = conn.cursor()
        cur.execute(sql, params)
        return cur
    return conn.execute(sql, params)


def _lastrowid(cur) -> int:
    if _pg():
        row = cur.fetchone()
        if row is None:
            return 0
        value = list(row.values())[0] if hasattr(row, "values") else row[0]
        return int(value)
    return int(cur.lastrowid)


def _encode_json_field(field: str, value: Any) -> Any:
    if field in STAGING_JSON_FIELDS:
        if field in JSON_LIST_FIELDS:
            if isinstance(value, str):
                return value
            return json.dumps(list(value or []), ensure_ascii=False)
        if field in JSON_DICT_FIELDS:
            if isinstance(value, str):
                return value
            return json.dumps(value or {}, ensure_ascii=False)
    return value


def _decode_json_value(field: str, value: Any) -> Any:
    if value in ("", None):
        return [] if field in JSON_LIST_FIELDS else {}
    if isinstance(value, (dict, list)):
        return value
    try:
        decoded = json.loads(value)
    except Exception:
        return [] if field in JSON_LIST_FIELDS else {}
    if field in JSON_LIST_FIELDS:
        return decoded if isinstance(decoded, list) else []
    return decoded if isinstance(decoded, dict) else {}


def _decode_staging_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return row
    decoded = dict(row)
    for field in STAGING_JSON_FIELDS:
        decoded[field] = _decode_json_value(field, decoded.get(field))
    for flag in ("needs_review", "is_confirmed", "is_reviewed"):
        if flag in decoded and decoded[flag] is not None:
            decoded[flag] = int(decoded[flag] or 0)
    if decoded.get("confidence") is not None:
        decoded["confidence"] = float(decoded["confidence"] or 0)
    return decoded


_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS organizations (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    status TEXT DEFAULT 'active',
    plan TEXT DEFAULT 'licensed',
    license_expires_at TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS app_users (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER REFERENCES organizations(id),
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS app_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS api_clients (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS api_key_hashes (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    client_id INTEGER NOT NULL REFERENCES api_clients(id),
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    last_used_at TEXT,
    revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER,
    api_key_id INTEGER,
    method TEXT,
    path TEXT,
    scope TEXT,
    status_code INTEGER,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS organization_settings (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id),
    api_base_url TEXT,
    contact_email TEXT,
    notes TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS document_submissions (
    id SERIAL PRIMARY KEY,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    api_key_id INTEGER REFERENCES api_key_hashes(id),
    university TEXT NOT NULL,
    admission_year TEXT,
    pdf_url TEXT,
    page_url TEXT,
    file_name TEXT,
    original_file_name TEXT,
    notes TEXT,
    processing_status TEXT DEFAULT 'submitted',
    document_id INTEGER,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS source_documents (
    id SERIAL PRIMARY KEY,
    university TEXT NOT NULL,
    pdf_url TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT,
    admission_year TEXT,
    status TEXT DEFAULT 'uploaded',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS document_pages (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER NOT NULL,
    image_path TEXT,
    status TEXT DEFAULT 'pending',
    raw_llm_json TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS admission_records_staging (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER,
    university TEXT,
    admission_year TEXT,
    admission_period TEXT,
    faculty TEXT,
    department TEXT,
    application_period TEXT,
    deadline_rule TEXT,
    eju_session TEXT,
    eju_japanese TEXT,
    eju_general TEXT,
    eju_math TEXT,
    eju_physics TEXT,
    eju_chemistry TEXT,
    eju_biology TEXT,
    english_requirement TEXT,
    screening_method TEXT,
    screening_schedule TEXT,
    result_date TEXT,
    enrollment_period TEXT,
    prefecture TEXT,
    campus TEXT,
    confidence REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 1,
    warnings_json TEXT DEFAULT '[]',
    is_confirmed INTEGER DEFAULT 0,
    raw_llm_json TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS admission_records (
    id SERIAL PRIMARY KEY,
    source_staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT,
    pdf_url TEXT,
    admission_year TEXT,
    admission_period TEXT,
    faculty TEXT,
    department TEXT,
    application_period TEXT,
    deadline_rule TEXT,
    eju_session TEXT,
    eju_japanese TEXT,
    eju_general TEXT,
    eju_math TEXT,
    eju_physics TEXT,
    eju_chemistry TEXT,
    eju_biology TEXT,
    english_requirement TEXT,
    screening_method TEXT,
    screening_schedule TEXT,
    result_date TEXT,
    enrollment_period TEXT,
    prefecture TEXT,
    campus TEXT,
    confirmed_by TEXT DEFAULT 'human',
    confirmed_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS correction_events (
    id SERIAL PRIMARY KEY,
    staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER,
    university TEXT,
    admission_year TEXT,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    page_number INTEGER,
    editor TEXT DEFAULT 'human_review',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE TABLE IF NOT EXISTS consultation_bookings (
    id SERIAL PRIMARY KEY,
    student_name TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT,
    role TEXT,
    target_year TEXT,
    program_id INTEGER REFERENCES admission_records(id),
    preferred_times TEXT,
    question TEXT,
    status TEXT DEFAULT 'new',
    owner_note TEXT,
    next_action_at TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_stg_doc ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac ON admission_records(faculty);
CREATE INDEX IF NOT EXISTS idx_corr_doc ON correction_events(document_id);
CREATE INDEX IF NOT EXISTS idx_corr_field ON correction_events(field_name);
CREATE INDEX IF NOT EXISTS idx_booking_program ON consultation_bookings(program_id);
CREATE INDEX IF NOT EXISTS idx_booking_status ON consultation_bookings(status);
CREATE INDEX IF NOT EXISTS idx_app_session_hash ON app_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_app_user_email ON app_users(email);
CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_key_hashes(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_usage_org ON api_usage_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_submission_org ON document_submissions(organization_id);
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS organizations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    slug TEXT UNIQUE,
    status TEXT DEFAULT 'active',
    plan TEXT DEFAULT 'licensed',
    license_expires_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS app_users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER REFERENCES organizations(id),
    email TEXT NOT NULL UNIQUE,
    display_name TEXT,
    role TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS app_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES app_users(id),
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS api_clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS api_key_hashes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    client_id INTEGER NOT NULL REFERENCES api_clients(id),
    key_prefix TEXT NOT NULL,
    key_hash TEXT NOT NULL UNIQUE,
    scopes_json TEXT DEFAULT '[]',
    status TEXT DEFAULT 'active',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    last_used_at TEXT,
    revoked_at TEXT
);
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER,
    api_key_id INTEGER,
    method TEXT,
    path TEXT,
    scope TEXT,
    status_code INTEGER,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS organization_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL UNIQUE REFERENCES organizations(id),
    api_base_url TEXT,
    contact_email TEXT,
    notes TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS document_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organization_id INTEGER NOT NULL REFERENCES organizations(id),
    api_key_id INTEGER REFERENCES api_key_hashes(id),
    university TEXT NOT NULL,
    admission_year TEXT,
    pdf_url TEXT,
    page_url TEXT,
    file_name TEXT,
    original_file_name TEXT,
    notes TEXT,
    processing_status TEXT DEFAULT 'submitted',
    document_id INTEGER REFERENCES source_documents(id),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    university TEXT NOT NULL,
    pdf_url TEXT,
    file_name TEXT NOT NULL,
    file_path TEXT,
    admission_year TEXT,
    status TEXT DEFAULT 'uploaded',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS document_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER NOT NULL,
    image_path TEXT,
    status TEXT DEFAULT 'pending',
    raw_llm_json TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS admission_records_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER,
    university TEXT,
    admission_year TEXT,
    admission_period TEXT,
    faculty TEXT,
    department TEXT,
    application_period TEXT,
    deadline_rule TEXT,
    eju_session TEXT,
    eju_japanese TEXT,
    eju_general TEXT,
    eju_math TEXT,
    eju_physics TEXT,
    eju_chemistry TEXT,
    eju_biology TEXT,
    english_requirement TEXT,
    screening_method TEXT,
    screening_schedule TEXT,
    result_date TEXT,
    enrollment_period TEXT,
    prefecture TEXT,
    campus TEXT,
    confidence REAL DEFAULT 0.0,
    needs_review INTEGER DEFAULT 1,
    warnings_json TEXT DEFAULT '[]',
    is_confirmed INTEGER DEFAULT 0,
    raw_llm_json TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS admission_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT,
    pdf_url TEXT,
    admission_year TEXT,
    admission_period TEXT,
    faculty TEXT,
    department TEXT,
    application_period TEXT,
    deadline_rule TEXT,
    eju_session TEXT,
    eju_japanese TEXT,
    eju_general TEXT,
    eju_math TEXT,
    eju_physics TEXT,
    eju_chemistry TEXT,
    eju_biology TEXT,
    english_requirement TEXT,
    screening_method TEXT,
    screening_schedule TEXT,
    result_date TEXT,
    enrollment_period TEXT,
    prefecture TEXT,
    campus TEXT,
    confirmed_by TEXT DEFAULT 'human',
    confirmed_at TEXT DEFAULT (datetime('now','localtime')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS correction_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT,
    admission_year TEXT,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    page_number INTEGER,
    editor TEXT DEFAULT 'human_review',
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE TABLE IF NOT EXISTS consultation_bookings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    student_name TEXT NOT NULL,
    contact_email TEXT,
    contact_phone TEXT,
    role TEXT,
    target_year TEXT,
    program_id INTEGER REFERENCES admission_records(id),
    preferred_times TEXT,
    question TEXT,
    status TEXT DEFAULT 'new',
    owner_note TEXT,
    next_action_at TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime'))
);
CREATE INDEX IF NOT EXISTS idx_stg_doc ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac ON admission_records(faculty);
CREATE INDEX IF NOT EXISTS idx_corr_doc ON correction_events(document_id);
CREATE INDEX IF NOT EXISTS idx_corr_field ON correction_events(field_name);
CREATE INDEX IF NOT EXISTS idx_booking_program ON consultation_bookings(program_id);
CREATE INDEX IF NOT EXISTS idx_booking_status ON consultation_bookings(status);
CREATE INDEX IF NOT EXISTS idx_app_session_hash ON app_sessions(token_hash);
CREATE INDEX IF NOT EXISTS idx_app_user_email ON app_users(email);
CREATE INDEX IF NOT EXISTS idx_api_key_hash ON api_key_hashes(key_hash);
CREATE INDEX IF NOT EXISTS idx_api_usage_org ON api_usage_logs(organization_id);
CREATE INDEX IF NOT EXISTS idx_submission_org ON document_submissions(organization_id);
"""

_STAGING_MIGRATION_COLUMNS = {
    "field_confidence": "TEXT DEFAULT '{}'",
    "field_evidence": "TEXT DEFAULT '{}'",
    "risk_level": "TEXT DEFAULT 'medium'",
    "manual_modified_fields": "TEXT DEFAULT '[]'",
    "is_reviewed": "INTEGER DEFAULT 0",
    "reviewed_at": "TEXT",
}

_BOOKING_MIGRATION_COLUMNS = {
    "owner_note": "TEXT",
    "next_action_at": "TEXT",
}


def _ensure_staging_columns(conn) -> None:
    if _pg():
        for column, definition in _STAGING_MIGRATION_COLUMNS.items():
            _execute(
                conn,
                f"ALTER TABLE admission_records_staging ADD COLUMN IF NOT EXISTS {column} {definition}",
            )
        return

    existing = {
        row["name"]
        for row in _fetchall(conn, "PRAGMA table_info(admission_records_staging)")
    }
    for column, definition in _STAGING_MIGRATION_COLUMNS.items():
        if column not in existing:
            _execute(conn, f"ALTER TABLE admission_records_staging ADD COLUMN {column} {definition}")


def _ensure_booking_columns(conn) -> None:
    if _pg():
        for column, definition in _BOOKING_MIGRATION_COLUMNS.items():
            _execute(
                conn,
                f"ALTER TABLE consultation_bookings ADD COLUMN IF NOT EXISTS {column} {definition}",
            )
        return

    existing = {
        row["name"]
        for row in _fetchall(conn, "PRAGMA table_info(consultation_bookings)")
    }
    for column, definition in _BOOKING_MIGRATION_COLUMNS.items():
        if column not in existing:
            _execute(conn, f"ALTER TABLE consultation_bookings ADD COLUMN {column} {definition}")


def _ensure_auth_seed() -> None:
    owner_org = get_or_create_organization("Owner Workspace")
    partner_org = get_or_create_organization(os.environ.get("PARTNER_ORG_NAME", "合作方"))
    owner_email = os.environ.get("OWNER_EMAIL", "").strip().lower()
    owner_password = os.environ.get("OWNER_PASSWORD", "")
    partner_email = os.environ.get("PARTNER_EMAIL", "").strip().lower()
    partner_password = os.environ.get("PARTNER_PASSWORD", "")
    if owner_email and owner_password:
        upsert_app_user(
            email=owner_email,
            password=owner_password,
            role="owner_admin",
            display_name=os.environ.get("OWNER_DISPLAY_NAME", "Owner"),
            organization_id=int(owner_org["id"]),
        )
    if partner_email and partner_password:
        upsert_app_user(
            email=partner_email,
            password=partner_password,
            role="partner_staff",
            display_name=os.environ.get("PARTNER_DISPLAY_NAME", "合作方负责人"),
            organization_id=int(partner_org["id"]),
        )


def init_db() -> None:
    conn = get_conn()
    if _pg():
        for stmt in [part.strip() for part in _SCHEMA_PG.split(";") if part.strip()]:
            _execute(conn, stmt)
    else:
        conn.executescript(_SCHEMA_SQLITE)
    _ensure_staging_columns(conn)
    _ensure_booking_columns(conn)
    conn.commit()
    conn.close()
    _ensure_auth_seed()
    runtime = get_db_runtime()
    print("DB initialised (PostgreSQL)" if runtime.mode == "postgres" else "DB initialised (SQLite)")
    if runtime.warning:
        print(f"DB warning: {runtime.warning}")


DEFAULT_API_SCOPES = [
    "programs:read",
    "recommendations:create",
    "bookings:create",
    "documents:submit",
    "documents:read_status",
]


def _hash_secret(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _hash_password(password: str, salt: str | None = None) -> str:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_value.encode("utf-8"), 120_000)
    return f"pbkdf2_sha256${salt_value}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        algo, salt, digest = stored.split("$", 2)
    except ValueError:
        return False
    if algo != "pbkdf2_sha256":
        return False
    return secrets.compare_digest(_hash_password(password, salt), stored)


def _clean_app_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    return {
        "id": int(row["id"]),
        "organization_id": int(row["organization_id"] or 0),
        "organization_name": row.get("organization_name") or "",
        "email": row.get("email") or "",
        "display_name": row.get("display_name") or "",
        "role": row.get("role") or "",
        "status": row.get("status") or "",
    }


def upsert_app_user(
    *,
    email: str,
    password: str,
    role: str,
    display_name: str = "",
    organization_id: int | None = None,
) -> dict[str, Any]:
    email_value = email.strip().lower()
    conn = get_conn()
    existing = _fetchone(conn, f"SELECT * FROM app_users WHERE email={_ph()}", (email_value,))
    password_hash = _hash_password(password)
    if existing:
        _execute(
            conn,
            f"UPDATE app_users SET organization_id={_ph()}, display_name={_ph()}, role={_ph()}, "
            f"password_hash={_ph()}, status={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (organization_id, display_name, role, password_hash, "active", _now(), int(existing["id"])),
        )
        user_id = int(existing["id"])
    else:
        sql = (
            "INSERT INTO app_users (organization_id,email,display_name,role,password_hash,status) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})"
        )
        if _pg():
            sql += " RETURNING id"
        cur = _execute(conn, sql, (organization_id, email_value, display_name, role, password_hash, "active"))
        user_id = _lastrowid(cur)
    conn.commit()
    row = _fetchone(
        conn,
        "SELECT u.*, o.name AS organization_name FROM app_users u "
        "LEFT JOIN organizations o ON o.id=u.organization_id "
        f"WHERE u.id={_ph()}",
        (user_id,),
    )
    conn.close()
    return _clean_app_user(row) or {}


def create_app_session(email: str, password: str) -> tuple[str, dict[str, Any]] | None:
    conn = get_conn()
    row = _fetchone(
        conn,
        "SELECT u.*, o.name AS organization_name FROM app_users u "
        "LEFT JOIN organizations o ON o.id=u.organization_id "
        f"WHERE u.email={_ph()} AND u.status={_ph()}",
        (email.strip().lower(), "active"),
    )
    if not row or not _verify_password(password, row.get("password_hash") or ""):
        conn.close()
        return None
    token = f"sess_{secrets.token_urlsafe(32)}"
    expires_at = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%S")
    _execute(
        conn,
        f"INSERT INTO app_sessions (user_id,token_hash,expires_at) VALUES ({_ph()},{_ph()},{_ph()})",
        (int(row["id"]), _hash_secret(token), expires_at),
    )
    conn.commit()
    conn.close()
    return token, _clean_app_user(row) or {}


def get_app_user_by_session(token: str) -> dict[str, Any] | None:
    token = (token or "").strip()
    if not token:
        return None
    conn = get_conn()
    row = _fetchone(
        conn,
        "SELECT u.*, o.name AS organization_name, s.expires_at FROM app_sessions s "
        "JOIN app_users u ON u.id=s.user_id "
        "LEFT JOIN organizations o ON o.id=u.organization_id "
        f"WHERE s.token_hash={_ph()} AND u.status={_ph()}",
        (_hash_secret(token), "active"),
    )
    if not row:
        conn.close()
        return None
    expires_at = str(row.get("expires_at") or "")
    if expires_at and expires_at < datetime.now().strftime("%Y-%m-%dT%H:%M:%S"):
        _execute(conn, f"DELETE FROM app_sessions WHERE token_hash={_ph()}", (_hash_secret(token),))
        conn.commit()
        conn.close()
        return None
    conn.close()
    return _clean_app_user(row)


def delete_app_session(token: str) -> None:
    if not token:
        return
    conn = get_conn()
    _execute(conn, f"DELETE FROM app_sessions WHERE token_hash={_ph()}", (_hash_secret(token),))
    conn.commit()
    conn.close()


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug or "organization"


def _hash_api_key(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _new_api_secret() -> str:
    return f"ak_{secrets.token_urlsafe(28)}"


def _json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if not value:
        return []
    try:
        decoded = json.loads(value)
    except Exception:
        return []
    return [str(item) for item in decoded] if isinstance(decoded, list) else []


def get_or_create_organization(name: str = "Owner Workspace") -> dict[str, Any]:
    slug = _slugify(name)
    conn = get_conn()
    row = _fetchone(conn, f"SELECT * FROM organizations WHERE slug={_ph()}", (slug,))
    if not row:
        sql = (
            f"INSERT INTO organizations (name,slug,status,plan) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()})"
        )
        if _pg():
            sql += " RETURNING id"
        cur = _execute(conn, sql, (name, slug, "active", "licensed"))
        org_id = _lastrowid(cur)
        _execute(
            conn,
            f"INSERT INTO organization_settings (organization_id,api_base_url,contact_email,notes) "
            f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()})",
            (org_id, "/v1", "", "Owner-issued API access"),
        )
        conn.commit()
        row = _fetchone(conn, f"SELECT * FROM organizations WHERE id={_ph()}", (org_id,))
    conn.close()
    return row or {}


def _get_or_create_api_client(conn, organization_id: int, name: str) -> dict[str, Any]:
    row = _fetchone(
        conn,
        f"SELECT * FROM api_clients WHERE organization_id={_ph()} AND name={_ph()}",
        (organization_id, name),
    )
    if row:
        return row
    sql = f"INSERT INTO api_clients (organization_id,name,status) VALUES ({_ph()},{_ph()},{_ph()})"
    if _pg():
        sql += " RETURNING id"
    cur = _execute(conn, sql, (organization_id, name, "active"))
    client_id = _lastrowid(cur)
    return _fetchone(conn, f"SELECT * FROM api_clients WHERE id={_ph()}", (client_id,)) or {}


def issue_api_key(
    organization_name: str = "Owner Workspace",
    client_name: str = "Default integration",
    scopes: list[str] | None = None,
) -> dict[str, Any]:
    organization = get_or_create_organization(organization_name)
    secret = _new_api_secret()
    scope_values = scopes or DEFAULT_API_SCOPES
    conn = get_conn()
    client = _get_or_create_api_client(conn, int(organization["id"]), client_name)
    sql = (
        "INSERT INTO api_key_hashes "
        f"(organization_id,client_id,key_prefix,key_hash,scopes_json,status) "
        f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})"
    )
    if _pg():
        sql += " RETURNING id"
    cur = _execute(
        conn,
        sql,
        (
            int(organization["id"]),
            int(client["id"]),
            secret[:12],
            _hash_api_key(secret),
            json.dumps(scope_values, ensure_ascii=False),
            "active",
        ),
    )
    key_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return {
        "key_id": key_id,
        "organization_id": int(organization["id"]),
        "client_id": int(client["id"]),
        "secret": secret,
        "masked_key": f"{secret[:12]}...",
        "scopes": scope_values,
    }


def revoke_api_key(key_id: int) -> bool:
    conn = get_conn()
    cur = _execute(
        conn,
        f"UPDATE api_key_hashes SET status={_ph()}, revoked_at={_ph()} WHERE id={_ph()}",
        ("revoked", _now(), int(key_id)),
    )
    changed = int(getattr(cur, "rowcount", 0) or 0)
    conn.commit()
    conn.close()
    return changed > 0


def get_api_key_context(secret: str) -> dict[str, Any] | None:
    secret = (secret or "").strip()
    if not secret:
        return None
    hashed = _hash_api_key(secret)
    conn = get_conn()
    row = _fetchone(
        conn,
        "SELECT k.id AS api_key_id, k.organization_id, k.client_id, k.key_prefix, "
        "k.scopes_json, k.status AS key_status, k.revoked_at, "
        "o.name AS organization_name, o.status AS organization_status, o.license_expires_at, "
        "c.name AS client_name, c.status AS client_status "
        "FROM api_key_hashes k "
        "JOIN organizations o ON o.id = k.organization_id "
        "JOIN api_clients c ON c.id = k.client_id "
        f"WHERE k.key_hash={_ph()}",
        (hashed,),
    )
    conn.close()
    if not row:
        return None
    row["scopes"] = _json_list(row.get("scopes_json"))
    return row


def mark_api_key_used(api_key_id: int) -> None:
    conn = get_conn()
    _execute(
        conn,
        f"UPDATE api_key_hashes SET last_used_at={_ph()} WHERE id={_ph()}",
        (_now(), int(api_key_id)),
    )
    conn.commit()
    conn.close()


def log_api_usage(
    organization_id: int | None,
    api_key_id: int | None,
    method: str,
    path: str,
    scope: str,
    status_code: int,
) -> None:
    conn = get_conn()
    _execute(
        conn,
        "INSERT INTO api_usage_logs "
        f"(organization_id,api_key_id,method,path,scope,status_code) "
        f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})",
        (organization_id, api_key_id, method, path, scope, int(status_code)),
    )
    conn.commit()
    conn.close()


def get_api_center(organization_id: int | None = None) -> dict[str, Any]:
    conn = get_conn()
    if organization_id:
        org = _fetchone(conn, f"SELECT * FROM organizations WHERE id={_ph()}", (int(organization_id),))
    else:
        org = _fetchone(conn, "SELECT * FROM organizations ORDER BY id LIMIT 1")
    if not org:
        conn.close()
        org = get_or_create_organization()
        conn = get_conn()
    settings = _fetchone(
        conn,
        f"SELECT api_base_url,contact_email,notes FROM organization_settings WHERE organization_id={_ph()}",
        (int(org["id"]),),
    ) or {"api_base_url": "/v1", "contact_email": "", "notes": ""}
    keys = _fetchall(
        conn,
        "SELECT k.id, k.key_prefix, k.scopes_json, k.status, k.created_at, k.last_used_at, "
        "c.name AS client_name "
        "FROM api_key_hashes k "
        "JOIN api_clients c ON c.id = k.client_id "
        f"WHERE k.organization_id={_ph()} ORDER BY k.id DESC",
        (int(org["id"]),),
    )
    usage = _fetchall(
        conn,
        "SELECT method,path,scope,status_code,created_at FROM api_usage_logs "
        f"WHERE organization_id={_ph()} ORDER BY id DESC LIMIT 20",
        (int(org["id"]),),
    )
    if organization_id:
        usage_summary = _fetchone(
            conn,
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) AS success, "
            "SUM(CASE WHEN status_code < 200 OR status_code >= 300 THEN 1 ELSE 0 END) AS needs_check "
            "FROM api_usage_logs "
            f"WHERE organization_id={_ph()}",
            (int(org["id"]),),
        ) or {"total": 0, "success": 0, "needs_check": 0}
        submission_summary_rows = _fetchall(
            conn,
            "SELECT processing_status AS status, COUNT(*) AS count "
            "FROM document_submissions "
            f"WHERE organization_id={_ph()} "
            "GROUP BY processing_status",
            (int(org["id"]),),
        )
    else:
        usage_summary = _fetchone(
            conn,
            "SELECT COUNT(*) AS total, "
            "SUM(CASE WHEN status_code >= 200 AND status_code < 300 THEN 1 ELSE 0 END) AS success, "
            "SUM(CASE WHEN status_code < 200 OR status_code >= 300 THEN 1 ELSE 0 END) AS needs_check "
            "FROM api_usage_logs",
            (),
        ) or {"total": 0, "success": 0, "needs_check": 0}
        submission_summary_rows = _fetchall(
            conn,
            "SELECT processing_status AS status, COUNT(*) AS count "
            "FROM document_submissions "
            "GROUP BY processing_status",
            (),
        )
    conn.close()
    submissions_by_status = {
        str(row.get("status") or "submitted"): int(row.get("count") or 0)
        for row in submission_summary_rows
    }
    submission_total = sum(submissions_by_status.values())
    return {
        "organization": {
            "id": int(org["id"]),
            "name": org.get("name") or "",
            "status": org.get("status") or "",
            "plan": org.get("plan") or "",
        },
        "settings": settings,
        "api_keys": [
            {
                "id": int(row["id"]),
                "client_name": row.get("client_name") or "",
                "masked_key": f"{row.get('key_prefix') or 'ak_'}...",
                "scopes": _json_list(row.get("scopes_json")),
                "status": row.get("status") or "",
                "created_at": row.get("created_at") or "",
                "last_used_at": row.get("last_used_at") or "",
            }
            for row in keys
        ],
        "recent_usage": usage,
        "usage_summary": {
            "total": int(usage_summary.get("total") or 0),
            "success": int(usage_summary.get("success") or 0),
            "needs_check": int(usage_summary.get("needs_check") or 0),
            "submission_total": submission_total,
            "submissions_by_status": submissions_by_status,
        },
        "allowed_scopes": DEFAULT_API_SCOPES,
    }


def create_document_submission(
    organization_id: int,
    api_key_id: int | None,
    payload: dict[str, Any],
) -> int:
    fields = [
        "organization_id",
        "api_key_id",
        "university",
        "admission_year",
        "pdf_url",
        "page_url",
        "file_name",
        "original_file_name",
        "notes",
        "processing_status",
    ]
    values = [
        int(organization_id),
        api_key_id,
        payload.get("university", ""),
        payload.get("admission_year", ""),
        payload.get("pdf_url", ""),
        payload.get("page_url", ""),
        payload.get("file_name", ""),
        payload.get("original_file_name", ""),
        payload.get("notes", ""),
        "submitted",
    ]
    sql = f"INSERT INTO document_submissions ({','.join(fields)}) VALUES ({_phn(len(fields))})"
    if _pg():
        sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, values)
    row_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return row_id


def get_document_submission(organization_id: int, submission_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    row = _fetchone(
        conn,
        "SELECT id,university,admission_year,pdf_url,page_url,file_name,original_file_name,"
        "notes,processing_status,document_id,created_at,updated_at "
        f"FROM document_submissions WHERE organization_id={_ph()} AND id={_ph()}",
        (int(organization_id), int(submission_id)),
    )
    conn.close()
    if row:
        row["status"] = row.get("processing_status")
    return row


OWNER_SUBMISSION_STATUSES = {
    "submitted",
    "processing",
    "needs_owner_review",
    "confirmed",
    "needs_more_info",
    "failed",
}


def _owner_submission_select() -> str:
    return (
        "SELECT s.id,s.university,s.admission_year,s.pdf_url,s.page_url,s.file_name,"
        "s.original_file_name,s.notes,s.processing_status,s.document_id,s.created_at,s.updated_at,"
        "o.name AS organization_name,c.name AS client_name "
        "FROM document_submissions s "
        "JOIN organizations o ON o.id=s.organization_id "
        "LEFT JOIN api_key_hashes k ON k.id=s.api_key_id "
        "LEFT JOIN api_clients c ON c.id=k.client_id "
    )


def _clean_owner_submission(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if not row:
        return None
    cleaned = dict(row)
    cleaned["status"] = cleaned.get("processing_status")
    return cleaned


def list_document_submissions(
    status: str | None = None,
    limit: int = 100,
    offset: int = 0,
    organization_id: int | None = None,
) -> list[dict[str, Any]]:
    params: list[Any] = []
    filters: list[str] = []
    if status:
        filters.append(f"s.processing_status={_ph()}")
        params.append(status)
    if organization_id:
        filters.append(f"s.organization_id={_ph()}")
        params.append(int(organization_id))
    where = f"WHERE {' AND '.join(filters)} " if filters else ""
    sql = (
        _owner_submission_select()
        + where
        + f"ORDER BY s.id DESC LIMIT {_ph()} OFFSET {_ph()}"
    )
    params.extend([int(limit), int(offset)])
    conn = get_conn()
    rows = _fetchall(conn, sql, tuple(params))
    conn.close()
    return [_clean_owner_submission(row) or {} for row in rows]


def get_document_submission_for_owner(submission_id: int) -> dict[str, Any] | None:
    conn = get_conn()
    row = _fetchone(
        conn,
        _owner_submission_select() + f"WHERE s.id={_ph()}",
        (int(submission_id),),
    )
    conn.close()
    return _clean_owner_submission(row)


def update_document_submission(
    submission_id: int,
    *,
    processing_status: str | None = None,
    document_id: int | None = None,
) -> dict[str, Any] | None:
    updates: dict[str, Any] = {"updated_at": _now()}
    if processing_status is not None:
        if processing_status not in OWNER_SUBMISSION_STATUSES:
            raise ValueError(f"Unsupported submission status: {processing_status}")
        updates["processing_status"] = processing_status
    if document_id is not None:
        updates["document_id"] = int(document_id)
    sets = ", ".join(f"{key}={_ph()}" for key in updates)
    conn = get_conn()
    _execute(
        conn,
        f"UPDATE document_submissions SET {sets} WHERE id={_ph()}",
        (*updates.values(), int(submission_id)),
    )
    conn.commit()
    conn.close()
    return get_document_submission_for_owner(submission_id)


def create_source_document(university, file_name, file_path="", pdf_url="", admission_year="") -> int:
    sql = (
        f"INSERT INTO source_documents (university,file_name,file_path,pdf_url,admission_year) "
        f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()})"
    )
    if _pg():
        sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, (university, file_name, file_path, pdf_url, admission_year))
    doc_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return doc_id


def update_source_document(doc_id, **kwargs):
    if not kwargs:
        return
    kwargs["updated_at"] = _now()
    sets = ", ".join(f"{key}={_ph()}" for key in kwargs)
    conn = get_conn()
    _execute(conn, f"UPDATE source_documents SET {sets} WHERE id={_ph()}", (*kwargs.values(), doc_id))
    conn.commit()
    conn.close()


def _canonical_university_name(value: str | None) -> str:
    text = str(value or "").strip()
    for old, new in {
        " ": "",
        "　": "",
        "\t": "",
        "\n": "",
        "稻": "稲",
    }.items():
        text = text.replace(old, new)
    text = re.sub(r"^[A-Za-z0-9_\-]+(?=[一-龥ぁ-んァ-ヴー])", "", text)
    return text


def insert_document_page(doc_id, page_number, image_path) -> int:
    sql = f"INSERT INTO document_pages (document_id,page_number,image_path,status) VALUES ({_ph()},{_ph()},{_ph()},'pending')"
    if _pg():
        sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, (doc_id, page_number, image_path))
    page_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return page_id


def update_document_page(page_id, status, raw_llm_json=""):
    conn = get_conn()
    _execute(
        conn,
        f"UPDATE document_pages SET status={_ph()}, raw_llm_json={_ph()} WHERE id={_ph()}",
        (status, raw_llm_json, page_id),
    )
    conn.commit()
    conn.close()


def insert_staging_record(doc_id, page_number, record) -> int:
    fields = [
        "document_id",
        "page_number",
        "university",
        "admission_year",
        "admission_period",
        "faculty",
        "department",
        "application_period",
        "deadline_rule",
        "eju_session",
        "eju_japanese",
        "eju_general",
        "eju_math",
        "eju_physics",
        "eju_chemistry",
        "eju_biology",
        "english_requirement",
        "screening_method",
        "screening_schedule",
        "result_date",
        "enrollment_period",
        "prefecture",
        "campus",
        "confidence",
        "needs_review",
        "warnings_json",
        "raw_llm_json",
        "field_confidence",
        "field_evidence",
        "risk_level",
        "manual_modified_fields",
        "is_reviewed",
        "reviewed_at",
    ]
    values: list[Any] = [doc_id, page_number]
    for field in fields[2:]:
        values.append(_encode_json_field(field, record.get(field, [] if field in JSON_LIST_FIELDS else {} if field in JSON_DICT_FIELDS else "")))

    sql = f"INSERT INTO admission_records_staging ({','.join(fields)}) VALUES ({_phn(len(fields))})"
    if _pg():
        sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, values)
    row_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return row_id


def get_staging_records(doc_id) -> list[dict]:
    conn = get_conn()
    rows = _fetchall(
        conn,
        f"SELECT * FROM admission_records_staging WHERE document_id={_ph()} ORDER BY id",
        (doc_id,),
    )
    conn.close()
    return [_decode_staging_row(row) for row in rows]


def get_staging_record(staging_id) -> dict | None:
    conn = get_conn()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={_ph()}", (staging_id,))
    conn.close()
    return _decode_staging_row(row)


def _stringify_event_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def _insert_correction_events(
    conn,
    *,
    staging_id: int,
    document_id: int | None,
    university: str,
    admission_year: str,
    page_number: int | None,
    changed_fields: list[tuple[str, Any, Any]],
) -> None:
    if not changed_fields:
        return
    sql = (
        "INSERT INTO correction_events "
        "(staging_id,document_id,university,admission_year,field_name,old_value,new_value,page_number,editor,created_at) "
        f"VALUES ({_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()},{_ph()})"
    )
    now = _now()
    for field, old_value, new_value in changed_fields:
        _execute(
            conn,
            sql,
            (
                staging_id,
                document_id,
                university,
                admission_year,
                field,
                _stringify_event_value(old_value),
                _stringify_event_value(new_value),
                page_number,
                "human_review",
                now,
            ),
        )


def update_staging_record(staging_id, data) -> dict | None:
    if not data:
        return get_staging_record(staging_id)

    allowed = {
        "document_id",
        "page_number",
        "university",
        "admission_year",
        "admission_period",
        "faculty",
        "department",
        "application_period",
        "deadline_rule",
        "eju_session",
        "eju_japanese",
        "eju_general",
        "eju_math",
        "eju_physics",
        "eju_chemistry",
        "eju_biology",
        "english_requirement",
        "screening_method",
        "screening_schedule",
        "result_date",
        "enrollment_period",
        "prefecture",
        "campus",
        "confidence",
        "needs_review",
        "warnings_json",
        "raw_llm_json",
        "is_confirmed",
        "field_confidence",
        "field_evidence",
        "risk_level",
        "manual_modified_fields",
        "is_reviewed",
        "reviewed_at",
    }
    patch = {key: value for key, value in data.items() if key in allowed}
    if not patch:
        return get_staging_record(staging_id)

    existing = get_staging_record(staging_id)
    if not existing:
        return None

    manual_modified = normalize_manual_modified_fields(
        patch.get("manual_modified_fields", existing.get("manual_modified_fields"))
    )

    changed_fields: list[tuple[str, Any, Any]] = []
    for field in TRACKABLE_FIELDS:
        if field in patch and str(existing.get(field) or "") != str(patch.get(field) or ""):
            manual_modified.append(field)
            changed_fields.append((field, existing.get(field), patch.get(field)))

    merged = dict(existing)
    merged.update(patch)
    merged["manual_modified_fields"] = list(dict.fromkeys(manual_modified))

    field_confidence = dict(existing.get("field_confidence") or {})
    field_evidence = dict(existing.get("field_evidence") or {})
    for field in TRACKABLE_FIELDS:
        if field in patch and str(existing.get(field) or "") != str(patch.get(field) or ""):
            field_confidence[field] = 1.0
            field_evidence[field] = {
                "text": str(patch.get(field) or ""),
                "page": existing.get("page_number"),
            }
    merged["field_confidence"] = field_confidence
    merged["field_evidence"] = field_evidence

    if merged.get("is_reviewed") and not merged.get("reviewed_at"):
        merged["reviewed_at"] = _now()
    merged["updated_at"] = _now()
    merged = validate(merged)

    fields = {key: _encode_json_field(key, value) for key, value in merged.items() if key in allowed or key in {"updated_at"}}
    sets = ", ".join(f"{key}={_ph()}" for key in fields)
    conn = get_conn()
    _execute(conn, f"UPDATE admission_records_staging SET {sets} WHERE id={_ph()}", (*fields.values(), staging_id))
    if "university" in patch and str(merged.get("university") or "").strip():
        _execute(
            conn,
            f"UPDATE source_documents SET university={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
            (str(merged.get("university") or "").strip(), merged["updated_at"], merged["document_id"]),
        )
    _insert_correction_events(
        conn,
        staging_id=staging_id,
        document_id=merged.get("document_id"),
        university=str(merged.get("university") or ""),
        admission_year=str(merged.get("admission_year") or ""),
        page_number=merged.get("page_number"),
        changed_fields=changed_fields,
    )
    conn.commit()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={_ph()}", (staging_id,))
    conn.close()
    return _decode_staging_row(row)


def delete_staging_record(staging_id) -> bool:
    conn = get_conn()
    _execute(conn, f"DELETE FROM correction_events WHERE staging_id={_ph()}", (staging_id,))
    _execute(conn, f"DELETE FROM admission_records_staging WHERE id={_ph()}", (staging_id,))
    conn.commit()
    conn.close()
    return True


def delete_document(doc_id: int) -> dict | None:
    conn = get_conn()
    doc = _fetchone(conn, f"SELECT * FROM source_documents WHERE id={_ph()}", (doc_id,))
    if not doc:
        conn.close()
        return None

    staging_ids = [
        row["id"]
        for row in _fetchall(
            conn,
            f"SELECT id FROM admission_records_staging WHERE document_id={_ph()}",
            (doc_id,),
        )
    ]
    deleted_records = 0
    if staging_ids:
        placeholders = _phn(len(staging_ids))
        _execute(
            conn,
            f"DELETE FROM correction_events WHERE document_id={_ph()} OR staging_id IN ({placeholders})",
            (doc_id, *staging_ids),
        )
        cur = _execute(
            conn,
            f"DELETE FROM admission_records WHERE document_id={_ph()} OR source_staging_id IN ({placeholders})",
            (doc_id, *staging_ids),
        )
        deleted_records = max(int(cur.rowcount or 0), 0)
    else:
        _execute(conn, f"DELETE FROM correction_events WHERE document_id={_ph()}", (doc_id,))
        cur = _execute(conn, f"DELETE FROM admission_records WHERE document_id={_ph()}", (doc_id,))
        deleted_records = max(int(cur.rowcount or 0), 0)

    cur = _execute(conn, f"DELETE FROM admission_records_staging WHERE document_id={_ph()}", (doc_id,))
    deleted_staging = max(int(cur.rowcount or 0), 0)
    cur = _execute(conn, f"DELETE FROM document_pages WHERE document_id={_ph()}", (doc_id,))
    deleted_pages = max(int(cur.rowcount or 0), 0)
    _execute(conn, f"DELETE FROM source_documents WHERE id={_ph()}", (doc_id,))
    conn.commit()
    conn.close()
    return {
        "doc_id": doc_id,
        "university": doc.get("university", ""),
        "admission_year": doc.get("admission_year", ""),
        "filename": doc.get("file_name", ""),
        "deleted_records": deleted_records,
        "deleted_staging": deleted_staging,
        "deleted_pages": deleted_pages,
    }


def prune_duplicate_documents(keep_doc_id: int) -> dict:
    conn = get_conn()
    keep = _fetchone(conn, f"SELECT id, university, admission_year FROM source_documents WHERE id={_ph()}", (keep_doc_id,))
    if not keep:
        conn.close()
        return {"kept_doc_id": keep_doc_id, "deleted_documents": []}

    keep_name = _canonical_university_name(keep.get("university"))
    keep_year = str(keep.get("admission_year") or "").strip()
    rows = _fetchall(
        conn,
        f"""
        SELECT id, university, admission_year
        FROM source_documents
        WHERE id <> {_ph()} AND COALESCE(admission_year,'') = {_ph()}
        ORDER BY id DESC
        """,
        (keep_doc_id, keep_year),
    )
    conn.close()

    duplicate_ids = [
        int(row["id"])
        for row in rows
        if _canonical_university_name(row.get("university")) == keep_name and keep_name
    ]
    deleted = []
    for duplicate_id in duplicate_ids:
        result = delete_document(duplicate_id)
        if result:
            deleted.append(result)
    return {"kept_doc_id": keep_doc_id, "deleted_documents": deleted}


def _confirm_row(conn, row: dict, pdf_url="") -> int:
    doc = _fetchone(conn, f"SELECT pdf_url FROM source_documents WHERE id={_ph()}", (row["document_id"],))
    doc_url = pdf_url or (doc["pdf_url"] if doc else "")
    sql = (
        "INSERT INTO admission_records ("
        "source_staging_id,document_id,university,pdf_url,admission_year,admission_period,"
        "faculty,department,application_period,deadline_rule,"
        "eju_session,eju_japanese,eju_general,eju_math,eju_physics,eju_chemistry,eju_biology,"
        "english_requirement,screening_method,screening_schedule,"
        "result_date,enrollment_period,prefecture,campus"
        f") VALUES ({_phn(24)})"
    )
    if _pg():
        sql += " RETURNING id"
    cur = _execute(
        conn,
        sql,
        (
            row["id"],
            row["document_id"],
            row["university"],
            doc_url,
            row["admission_year"],
            row["admission_period"],
            row["faculty"],
            row["department"],
            row["application_period"],
            row["deadline_rule"],
            row["eju_session"],
            row["eju_japanese"],
            row["eju_general"],
            row["eju_math"],
            row["eju_physics"],
            row["eju_chemistry"],
            row["eju_biology"],
            row["english_requirement"],
            row["screening_method"],
            row["screening_schedule"],
            row["result_date"],
            row["enrollment_period"],
            row["prefecture"],
            row["campus"],
        ),
    )
    return _lastrowid(cur)


def confirm_staging_record(staging_id, pdf_url="") -> int:
    conn = get_conn()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={_ph()}", (staging_id,))
    if not row:
        conn.close()
        return 0
    row = _decode_staging_row(row)
    if row.get("risk_level") == "high" and not row.get("is_reviewed"):
        conn.close()
        return 0
    new_id = _confirm_row(conn, row, pdf_url)
    _execute(
        conn,
        f"UPDATE admission_records_staging SET is_confirmed=1, is_reviewed=1, reviewed_at={_ph()}, updated_at={_ph()} WHERE id={_ph()}",
        (_now(), _now(), staging_id),
    )
    conn.commit()
    conn.close()
    return new_id


def confirm_all_by_doc(doc_id, pdf_url="") -> dict:
    conn = get_conn()
    rows = _fetchall(
        conn,
        f"SELECT * FROM admission_records_staging WHERE document_id={_ph()} ORDER BY "
        "CASE COALESCE(risk_level,'medium') WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END, "
        "COALESCE(confidence,0) DESC, id DESC",
        (doc_id,),
    )
    if not rows:
        conn.close()
        return {"processed": 0, "written": 0, "skipped": 0}

    decoded_rows = [_decode_staging_row(row) for row in rows]
    best: dict[tuple, dict] = {}
    for row in decoded_rows:
        key = (
            (row.get("university") or "").strip(),
            (row.get("admission_year") or "").strip(),
            (row.get("faculty") or "").strip(),
            (row.get("department") or "").strip(),
        )
        if key not in best or float(row.get("confidence") or 0) > float(best[key].get("confidence") or 0):
            best[key] = row

    existing = _fetchall(
        conn,
        f"SELECT university,admission_year,faculty,department FROM admission_records WHERE document_id={_ph()}",
        (doc_id,),
    )
    existing_keys = {
        (
            (row["university"] or "").strip(),
            (row["admission_year"] or "").strip(),
            (row["faculty"] or "").strip(),
            (row["department"] or "").strip(),
        )
        for row in existing
    }

    written = 0
    skipped = 0
    now = _now()

    for key, row in best.items():
        if row.get("risk_level") == "high" and not row.get("is_reviewed"):
            skipped += 1
            continue
        if key in existing_keys:
            skipped += 1
            continue
        _confirm_row(conn, row, pdf_url)
        written += 1

    for row in decoded_rows:
        if row.get("risk_level") == "high" and not row.get("is_reviewed"):
            continue
        _execute(
            conn,
            f"UPDATE admission_records_staging SET is_confirmed=1, updated_at={_ph()} WHERE id={_ph()}",
            (now, row["id"]),
        )

    conn.commit()
    conn.close()
    return {"processed": len(decoded_rows), "written": written, "skipped": skipped}


RECORD_SELECT_COLUMNS = (
    "id,university,admission_year,faculty,department,"
    "admission_period,application_period,deadline_rule,eju_session,eju_japanese,eju_general,"
    "eju_math,eju_physics,eju_chemistry,eju_biology,english_requirement,"
    "screening_method,screening_schedule,result_date,enrollment_period,prefecture,campus"
)


def _clean_filter_values(values: list[str] | tuple[str, ...] | None) -> list[str]:
    return [str(value).strip() for value in values or [] if str(value or "").strip()]


def get_export_records(
    *,
    universities: list[str] | None = None,
    years: list[str] | None = None,
    faculties: list[str] | None = None,
    record_ids: list[int] | None = None,
    limit: int = 10000,
    offset: int = 0,
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    like = "ILIKE" if _pg() else "LIKE"
    university_values = _clean_filter_values(universities)
    year_values = _clean_filter_values(years)
    faculty_values = _clean_filter_values(faculties)
    id_values = [int(value) for value in record_ids or [] if str(value or "").strip()]

    if id_values:
        clauses.append(f"id IN ({_phn(len(id_values))})")
        params.extend(id_values)
    if university_values:
        clauses.append("(" + " OR ".join(f"university {like} {_ph()}" for _ in university_values) + ")")
        params.extend(f"%{value}%" for value in university_values)
    if year_values:
        clauses.append(f"admission_year IN ({_phn(len(year_values))})")
        params.extend(year_values)
    if faculty_values:
        clauses.append("(" + " OR ".join(f"faculty {like} {_ph()}" for _ in faculty_values) + ")")
        params.extend(f"%{value}%" for value in faculty_values)

    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([int(limit), int(offset)])
    sql = f"SELECT {RECORD_SELECT_COLUMNS} FROM admission_records {where} ORDER BY university, admission_year DESC, faculty, department, id LIMIT {_ph()} OFFSET {_ph()}"
    conn = get_conn()
    rows = _fetchall(conn, sql, tuple(params))
    conn.close()
    return rows


def get_export_options(limit: int = 200) -> dict[str, list[dict[str, Any]]]:
    conn = get_conn()
    try:
        universities = _fetchall(
            conn,
            f"""
            SELECT university AS value, COUNT(*) AS count
            FROM admission_records
            WHERE COALESCE(university, '') <> ''
            GROUP BY university
            ORDER BY COUNT(*) DESC, university
            LIMIT {_ph()}
            """,
            (int(limit),),
        )
        years = _fetchall(
            conn,
            f"""
            SELECT admission_year AS value, COUNT(*) AS count
            FROM admission_records
            WHERE COALESCE(admission_year, '') <> ''
            GROUP BY admission_year
            ORDER BY admission_year DESC
            LIMIT {_ph()}
            """,
            (int(limit),),
        )
        faculties = _fetchall(
            conn,
            f"""
            SELECT faculty AS value, COUNT(*) AS count
            FROM admission_records
            WHERE COALESCE(faculty, '') <> ''
            GROUP BY faculty
            ORDER BY COUNT(*) DESC, faculty
            LIMIT {_ph()}
            """,
            (int(limit),),
        )
    finally:
        conn.close()
    return {"universities": universities, "years": years, "faculties": faculties}


def get_records(university=None, year=None, faculty=None, limit=100, offset=0) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    like = "ILIKE" if _pg() else "LIKE"
    if university:
        clauses.append(f"university {like} {_ph()}")
        params.append(f"%{university}%")
    if year is not None:
        clauses.append(f"admission_year = {_ph()}")
        params.append(str(year))
    if faculty:
        clauses.append(f"faculty {like} {_ph()}")
        params.append(f"%{faculty}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    sql = f"SELECT {RECORD_SELECT_COLUMNS} FROM admission_records {where} ORDER BY id DESC LIMIT {_ph()} OFFSET {_ph()}"
    conn = get_conn()
    rows = _fetchall(conn, sql, params)
    conn.close()
    return rows


def _public_risk(row: dict[str, Any]) -> dict[str, Any]:
    missing = []
    for field, label in (
        ("application_period", "出愿期间"),
        ("deadline_rule", "截止规则"),
        ("screening_method", "选考方式"),
        ("result_date", "合格发表日"),
    ):
        if not str(row.get(field) or "").strip():
            missing.append(label)
    complex_bits = []
    haystack = " ".join(str(row.get(field) or "") for field in ("eju_japanese", "eju_general", "eju_math", "eju_physics", "eju_chemistry", "eju_biology", "english_requirement"))
    if any(marker in haystack for marker in ("要確認", "确认", "選択", "任选", "から", "または", "／", "/")):
        complex_bits.append("要求中含有选择或需确认条件")
    if missing:
        return {"level": "high" if len(missing) >= 3 else "medium", "reasons": [f"缺少{item}" for item in missing] + complex_bits}
    if complex_bits:
        return {"level": "medium", "reasons": complex_bits}
    return {"level": "low", "reasons": ["已确认记录，核心字段较完整"]}


def _public_program_from_row(row: dict[str, Any]) -> dict[str, Any]:
    risk = _public_risk(row)
    stored_risk_level = str(row.get("staging_risk_level") or "").strip()
    if stored_risk_level:
        risk["level"] = stored_risk_level
    field_evidence = _decode_json_value("field_evidence", row.get("field_evidence"))
    confidence_value = row.get("staging_confidence")
    try:
        confidence = float(confidence_value) if confidence_value not in ("", None) else None
    except (TypeError, ValueError):
        confidence = None
    return {
        "id": int(row.get("id") or 0),
        "school_name": row.get("university") or "",
        "admission_year": row.get("admission_year") or "",
        "admission_period": row.get("admission_period") or "",
        "faculty": row.get("faculty") or "",
        "department": row.get("department") or "",
        "application_period": row.get("application_period") or "",
        "deadline_rule": row.get("deadline_rule") or "",
        "exam_method": row.get("screening_method") or "",
        "exam_date": row.get("screening_schedule") or "",
        "result_date": row.get("result_date") or "",
        "enrollment_period": row.get("enrollment_period") or "",
        "prefecture": row.get("prefecture") or "",
        "campus": row.get("campus") or "",
        "requirements": {
            "eju": {
                "session": row.get("eju_session") or "",
                "japanese": row.get("eju_japanese") or "",
                "general": row.get("eju_general") or "",
                "math": row.get("eju_math") or "",
                "physics": row.get("eju_physics") or "",
                "chemistry": row.get("eju_chemistry") or "",
                "biology": row.get("eju_biology") or "",
            },
            "english": {"raw_text": row.get("english_requirement") or ""},
            "jlpt": {"raw_text": ""},
            "eligibility": "",
            "required_documents": [],
        },
        "risk": risk,
        "risk_level": risk.get("level"),
        "confidence": confidence,
        "evidence": field_evidence,
        "source_document": {
            "id": row.get("document_id"),
            "file_name": row.get("source_file_name") or "",
            "pdf_url": row.get("source_pdf_url") or row.get("pdf_url") or "",
        },
    }


def get_public_programs(
    university: str | None = None,
    year: str | int | None = None,
    faculty: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    like = "ILIKE" if _pg() else "LIKE"
    if university:
        clauses.append(f"ar.university {like} {_ph()}")
        params.append(f"%{university}%")
    if year:
        clauses.append(f"ar.admission_year = {_ph()}")
        params.append(str(year))
    if faculty:
        clauses.append(f"ar.faculty {like} {_ph()}")
        params.append(f"%{faculty}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([int(limit), int(offset)])
    sql = (
        "SELECT ar.id, ar.document_id, ar.university, ar.pdf_url, ar.admission_year, "
        "ar.admission_period, ar.faculty, ar.department, ar.application_period, ar.deadline_rule, "
        "ar.eju_session, ar.eju_japanese, ar.eju_general, ar.eju_math, ar.eju_physics, "
        "ar.eju_chemistry, ar.eju_biology, ar.english_requirement, ar.screening_method, "
        "ar.screening_schedule, ar.result_date, ar.enrollment_period, ar.prefecture, ar.campus, "
        "sd.file_name AS source_file_name, sd.pdf_url AS source_pdf_url, "
        "st.confidence AS staging_confidence, st.field_evidence, st.risk_level AS staging_risk_level "
        "FROM admission_records ar "
        "LEFT JOIN source_documents sd ON sd.id = ar.document_id "
        f"LEFT JOIN admission_records_staging st ON st.id = ar.source_staging_id {where} "
        f"ORDER BY ar.id DESC LIMIT {_ph()} OFFSET {_ph()}"
    )
    conn = get_conn()
    rows = _fetchall(conn, sql, tuple(params))
    conn.close()
    return [_public_program_from_row(row) for row in rows]


def get_public_program(program_id: int) -> dict[str, Any] | None:
    sql = (
        "SELECT ar.id, ar.document_id, ar.university, ar.pdf_url, ar.admission_year, "
        "ar.admission_period, ar.faculty, ar.department, ar.application_period, ar.deadline_rule, "
        "ar.eju_session, ar.eju_japanese, ar.eju_general, ar.eju_math, ar.eju_physics, "
        "ar.eju_chemistry, ar.eju_biology, ar.english_requirement, ar.screening_method, "
        "ar.screening_schedule, ar.result_date, ar.enrollment_period, ar.prefecture, ar.campus, "
        "sd.file_name AS source_file_name, sd.pdf_url AS source_pdf_url, "
        "st.confidence AS staging_confidence, st.field_evidence, st.risk_level AS staging_risk_level "
        "FROM admission_records ar "
        "LEFT JOIN source_documents sd ON sd.id = ar.document_id "
        f"LEFT JOIN admission_records_staging st ON st.id = ar.source_staging_id WHERE ar.id = {_ph()}"
    )
    conn = get_conn()
    row = _fetchone(conn, sql, (int(program_id),))
    conn.close()
    return _public_program_from_row(row) if row else None


def _profile_terms(values: Any) -> list[str]:
    if isinstance(values, str):
        return [values.strip()] if values.strip() else []
    if isinstance(values, list):
        return [str(value).strip() for value in values if str(value or "").strip()]
    return []


def _contains_term(text: str, term: str) -> bool:
    lowered = str(text or "").lower()
    cleaned = str(term or "").strip().lower()
    return bool(cleaned and cleaned in lowered)


def _risk_rank(value: str) -> int:
    if value == "low":
        return 0
    if value == "medium":
        return 1
    return 2


def recommend_public_programs(profile: dict[str, Any], *, limit: int = 20) -> dict[str, Any]:
    programs = get_public_programs(year=profile.get("target_year") or None, limit=500, offset=0)
    if not programs and profile.get("target_year"):
        programs = get_public_programs(limit=500, offset=0)
    desired_fields = _profile_terms(profile.get("desired_fields"))
    preferred_prefectures = _profile_terms(profile.get("preferred_prefectures"))
    english_tests = [item.lower() for item in _profile_terms(profile.get("english_tests"))]
    eju_subjects = _profile_terms(profile.get("eju_subjects"))

    results: list[dict[str, Any]] = []
    for program in programs:
        score = 0
        reasons: list[str] = []
        check_items: list[str] = []
        searchable = " ".join(
            str(program.get(key) or "")
            for key in ("school_name", "faculty", "department", "prefecture", "campus", "exam_method")
        )
        requirements = program.get("requirements") or {}
        eju = requirements.get("eju") or {}
        english = (requirements.get("english") or {}).get("raw_text") or ""
        eju_text = " ".join(str(value or "") for value in eju.values())

        if profile.get("target_year") and str(program.get("admission_year")) == str(profile.get("target_year")):
            score += 18
            reasons.append(f"{profile.get('target_year')} 年度可以先看")
        for term in desired_fields:
            if _contains_term(searchable, term):
                score += 28
                reasons.append(f"方向里有“{term}”")
        for term in preferred_prefectures:
            if _contains_term(searchable, term):
                score += 18
                reasons.append(f"地区接近“{term}”")
        for term in english_tests:
            if _contains_term(english, term):
                score += 12
                reasons.append(f"英语要求中出现 {term.upper()}")
        for term in eju_subjects:
            if _contains_term(eju_text, term):
                score += 10
                reasons.append(f"EJU 条件提到“{term}”")

        risk_level = str((program.get("risk") or {}).get("level") or "medium")
        if risk_level == "low":
            score += 8
        elif risk_level == "high":
            score -= 18
        if risk_level == "high":
            check_items.append("这所学校的要求还有不完整或复杂的地方，咨询前需要再看原文")
        elif risk_level == "medium":
            check_items.append("有选择条件或需要进一步确认的地方")
        if not english:
            check_items.append("英语要求没有写清楚，需要确认是否不要求")
        if not eju_text.strip():
            check_items.append("EJU 要求没有写清楚，需要确认是否不要求")
        if not reasons:
            reasons.append("可以作为备选先看，具体条件再确认")

        if score >= 62 and risk_level == "low":
            fit_level = "likely_fit"
        elif score >= 24 and risk_level != "high":
            fit_level = "check_carefully"
        else:
            fit_level = "high_risk"
        results.append(
            {
                "program": program,
                "score": score,
                "fit_level": fit_level,
                "reasons": reasons,
                "check_items": check_items or ["请顾问确认最新募集要项和个人成绩条件"],
            }
        )

    fit_rank = {"likely_fit": 0, "check_carefully": 1, "high_risk": 2}
    results.sort(
        key=lambda item: (
            fit_rank.get(str(item["fit_level"]), 3),
            _risk_rank(str((item["program"].get("risk") or {}).get("level") or "medium")),
            -int(item["score"]),
            str(item["program"].get("school_name") or ""),
        )
    )
    return {"profile": profile, "results": results[: int(limit)]}


def create_consultation_booking(payload: dict[str, Any]) -> int:
    fields = [
        "student_name",
        "contact_email",
        "contact_phone",
        "role",
        "target_year",
        "program_id",
        "preferred_times",
        "question",
        "status",
    ]
    values = [payload.get(field, "") for field in fields]
    sql = f"INSERT INTO consultation_bookings ({','.join(fields)}) VALUES ({_phn(len(fields))})"
    if _pg():
        sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, values)
    row_id = _lastrowid(cur)
    conn.commit()
    conn.close()
    return row_id


def list_consultation_bookings(
    *,
    status: str | None = None,
    q: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: list[Any] = []
    if status:
        clauses.append(f"cb.status={_ph()}")
        params.append(status)
    query = str(q or "").strip()
    if query:
        like = f"%{query.lower()}%"
        searchable = [
            "cb.student_name",
            "cb.contact_email",
            "cb.contact_phone",
            "cb.role",
            "cb.target_year",
            "cb.preferred_times",
            "cb.question",
            "cb.owner_note",
            "cb.next_action_at",
            "ar.university",
            "ar.faculty",
            "ar.department",
            "ar.admission_year",
        ]
        clauses.append("(" + " OR ".join(f"LOWER(COALESCE({column}, '')) LIKE {_ph()}" for column in searchable) + ")")
        params.extend([like] * len(searchable))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([int(limit), int(offset)])
    sql = f"""
        SELECT
            cb.id,
            cb.student_name,
            cb.contact_email,
            cb.contact_phone,
            cb.role,
            cb.target_year,
            cb.program_id,
            cb.preferred_times,
            cb.question,
            cb.status,
            cb.owner_note,
            cb.next_action_at,
            cb.created_at,
            ar.university AS school_name,
            ar.faculty,
            ar.department,
            ar.admission_year
        FROM consultation_bookings cb
        LEFT JOIN admission_records ar ON ar.id = cb.program_id
        {where}
        ORDER BY cb.created_at DESC, cb.id DESC
        LIMIT {_ph()} OFFSET {_ph()}
    """
    conn = get_conn()
    rows = _fetchall(conn, sql, tuple(params))
    conn.close()
    return rows


def update_consultation_booking(
    booking_id: int,
    *,
    status: str | None = None,
    owner_note: str | None = None,
    next_action_at: str | None = None,
) -> dict[str, Any] | None:
    assignments: list[str] = []
    params: list[Any] = []
    if status is not None:
        assignments.append(f"status={_ph()}")
        params.append(status)
    if owner_note is not None:
        assignments.append(f"owner_note={_ph()}")
        params.append(owner_note)
    if next_action_at is not None:
        assignments.append(f"next_action_at={_ph()}")
        params.append(next_action_at)
    if not assignments:
        assignments.append("id=id")
    conn = get_conn()
    params.append(int(booking_id))
    _execute(conn, f"UPDATE consultation_bookings SET {', '.join(assignments)} WHERE id={_ph()}", tuple(params))
    conn.commit()
    row = _fetchone(
        conn,
        f"""
        SELECT
            cb.id,
            cb.student_name,
            cb.contact_email,
            cb.contact_phone,
            cb.role,
            cb.target_year,
            cb.program_id,
            cb.preferred_times,
            cb.question,
            cb.status,
            cb.owner_note,
            cb.next_action_at,
            cb.created_at,
            ar.university AS school_name,
            ar.faculty,
            ar.department,
            ar.admission_year
        FROM consultation_bookings cb
        LEFT JOIN admission_records ar ON ar.id = cb.program_id
        WHERE cb.id={_ph()}
        """,
        (int(booking_id),),
    )
    conn.close()
    return row


def get_stats() -> dict:
    conn = get_conn()
    total = (_fetchone(conn, "SELECT COUNT(*) AS c FROM admission_records") or {}).get("c", 0)
    staging = (_fetchone(conn, "SELECT COUNT(*) AS c FROM admission_records_staging") or {}).get("c", 0)
    univs = (
        _fetchone(
            conn,
            "SELECT COUNT(DISTINCT university) AS c FROM admission_records WHERE TRIM(COALESCE(university,''))<>''",
        )
        or {}
    ).get("c", 0)
    if _pg():
        avg = (_fetchone(conn, "SELECT ROUND(AVG(confidence)::numeric,2) AS c FROM admission_records_staging") or {}).get("c", 0)
    else:
        avg = (_fetchone(conn, "SELECT ROUND(AVG(confidence),2) AS c FROM admission_records_staging") or {}).get("c", 0)
    conn.close()
    return {
        "total_records": int(total or 0),
        "staging_records": int(staging or 0),
        "universities": int(univs or 0),
        "avg_confidence": float(avg or 0),
    }


def _confidence_bucket(value: float | int | None) -> str:
    if value is None:
        return "unknown"
    score = float(value)
    if score < 0.60:
        return "<0.60"
    if score < 0.70:
        return "0.60-0.69"
    if score < 0.80:
        return "0.70-0.79"
    if score < 0.90:
        return "0.80-0.89"
    if score < 0.95:
        return "0.90-0.94"
    return "0.95+"


def get_quality_metrics(doc_id: int | None = None) -> dict[str, Any]:
    conn = get_conn()
    params: list[Any] = []
    where = ""
    if doc_id is not None:
        where = f"WHERE s.document_id={_ph()}"
        params.append(int(doc_id))

    total_row = _fetchone(
        conn,
        f"SELECT COUNT(*) AS c FROM admission_records_staging s {where}",
        tuple(params),
    ) or {}
    total_records = int(total_row.get("c") or 0)

    risk_rows = _fetchall(
        conn,
        f"""
        SELECT COALESCE(NULLIF(TRIM(COALESCE(s.risk_level,'')),''),'medium') AS risk_level, COUNT(*) AS c
        FROM admission_records_staging s
        {where}
        GROUP BY COALESCE(NULLIF(TRIM(COALESCE(s.risk_level,'')),''),'medium')
        """,
        tuple(params),
    )
    risk_distribution = {"high": 0, "medium": 0, "low": 0}
    for row in risk_rows:
        key = str(row.get("risk_level") or "medium")
        risk_distribution[key] = int(row.get("c") or 0)

    coverage: list[dict[str, Any]] = []
    ce_doc_filter = ""
    ce_doc_params: tuple[Any, ...] = tuple()
    if doc_id is not None:
        ce_doc_filter = f"AND ce.document_id={_ph()}"
        ce_doc_params = (int(doc_id),)

    for field in QUALITY_FIELDS:
        filled_row = _fetchone(
            conn,
            f"""
            SELECT COUNT(*) AS c
            FROM admission_records_staging s
            {where} {'AND' if where else 'WHERE'} TRIM(COALESCE(s.{field},''))<>''
            """,
            tuple(params),
        ) or {}
        modified_row = _fetchone(
            conn,
            f"""
            SELECT COUNT(DISTINCT ce.staging_id) AS c
            FROM correction_events ce
            WHERE ce.field_name={_ph()} {ce_doc_filter}
            """,
            (field, *ce_doc_params),
        ) or {}
        filled = int(filled_row.get("c") or 0)
        modified = int(modified_row.get("c") or 0)
        coverage.append(
            {
                "field": field,
                "filled": filled,
                "fill_rate": round((filled / total_records) if total_records else 0.0, 4),
                "modified": modified,
                "modified_rate": round((modified / total_records) if total_records else 0.0, 4),
            }
        )

    correction_where = ""
    correction_params: tuple[Any, ...] = ()
    if doc_id is not None:
        correction_where = f"WHERE ce.document_id={_ph()}"
        correction_params = (int(doc_id),)
    top_modified = _fetchall(
        conn,
        f"""
        SELECT ce.field_name, COUNT(*) AS c
        FROM correction_events ce
        {correction_where}
        GROUP BY ce.field_name
        ORDER BY c DESC
        LIMIT 10
        """,
        correction_params,
    )

    rows = _fetchall(
        conn,
        f"""
        SELECT s.id, COALESCE(s.confidence,0) AS confidence,
               CASE WHEN ce.staging_id IS NULL THEN 0 ELSE 1 END AS corrected
        FROM admission_records_staging s
        LEFT JOIN (
            SELECT DISTINCT staging_id
            FROM correction_events
        ) ce ON ce.staging_id = s.id
        {where}
        """,
        tuple(params),
    )
    bucket_counts: dict[str, dict[str, int]] = {}
    for row in rows:
        bucket = _confidence_bucket(row.get("confidence"))
        payload = bucket_counts.setdefault(bucket, {"total": 0, "corrected": 0})
        payload["total"] += 1
        payload["corrected"] += int(row.get("corrected") or 0)

    bucket_order = ["<0.60", "0.60-0.69", "0.70-0.79", "0.80-0.89", "0.90-0.94", "0.95+", "unknown"]
    calibration = []
    for bucket in bucket_order:
        info = bucket_counts.get(bucket)
        if not info:
            continue
        total = info["total"]
        corrected = info["corrected"]
        calibration.append(
            {
                "bucket": bucket,
                "total": total,
                "corrected": corrected,
                "corrected_rate": round((corrected / total) if total else 0.0, 4),
            }
        )

    conn.close()
    return {
        "doc_id": doc_id,
        "total_staging_records": total_records,
        "risk_distribution": risk_distribution,
        "field_coverage": coverage,
        "confidence_calibration": calibration,
        "top_modified_fields": [
            {"field": str(row.get("field_name") or ""), "count": int(row.get("c") or 0)}
            for row in top_modified
        ],
    }


def get_correction_events(doc_id: int | None = None, limit: int = 100) -> list[dict[str, Any]]:
    conn = get_conn()
    params: list[Any] = []
    where = ""
    if doc_id is not None:
        where = f"WHERE document_id={_ph()}"
        params.append(int(doc_id))
    params.append(max(1, min(int(limit or 100), 1000)))
    rows = _fetchall(
        conn,
        f"""
        SELECT id,staging_id,document_id,university,admission_year,field_name,old_value,new_value,page_number,editor,created_at
        FROM correction_events
        {where}
        ORDER BY id DESC
        LIMIT {_ph()}
        """,
        tuple(params),
    )
    conn.close()
    return rows


def get_documents(query: str | None = None, year: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    like = "ILIKE" if _pg() else "LIKE"
    if query:
        q = f"%{query}%"
        clauses.append(
            f"(sd.university {like} {_ph()} OR sd.file_name {like} {_ph()} OR COALESCE(sd.pdf_url,'') {like} {_ph()})"
        )
        params.extend([q, q, q])
    if year:
        clauses.append(f"sd.admission_year = {_ph()}")
        params.append(str(year))
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    sql = f"""
        SELECT
            sd.id AS doc_id,
            sd.university AS university_name,
            sd.admission_year,
            sd.pdf_url AS source_url,
            sd.file_name AS filename,
            sd.status,
            sd.created_at,
            COALESCE(st.staging_count, 0) AS staging_count,
            COALESCE(cf.confirmed_count, 0) AS confirmed_count
        FROM source_documents sd
        LEFT JOIN (
            SELECT document_id, COUNT(*) AS staging_count
            FROM admission_records_staging
            GROUP BY document_id
        ) st ON st.document_id = sd.id
        LEFT JOIN (
            SELECT document_id, COUNT(*) AS confirmed_count
            FROM admission_records
            GROUP BY document_id
        ) cf ON cf.document_id = sd.id
        {where}
        ORDER BY sd.id DESC
        LIMIT {_ph()} OFFSET {_ph()}
    """
    conn = get_conn()
    rows = _fetchall(conn, sql, params)
    conn.close()
    return rows


def get_document_summary(doc_id: int) -> dict | None:
    sql = f"""
        SELECT
            sd.id AS doc_id,
            sd.university AS university_name,
            sd.admission_year,
            sd.pdf_url AS source_url,
            sd.file_name AS filename,
            sd.status,
            sd.created_at,
            COALESCE(st.staging_count, 0) AS staging_count,
            COALESCE(st.review_count, 0) AS review_count,
            COALESCE(cf.confirmed_count, 0) AS confirmed_count,
            COALESCE(st.avg_confidence, 0) AS avg_confidence
        FROM source_documents sd
        LEFT JOIN (
            SELECT
                document_id,
                COUNT(*) AS staging_count,
                SUM(CASE WHEN COALESCE(needs_review, 0) <> 0 THEN 1 ELSE 0 END) AS review_count,
                AVG(confidence) AS avg_confidence
            FROM admission_records_staging
            GROUP BY document_id
        ) st ON st.document_id = sd.id
        LEFT JOIN (
            SELECT document_id, COUNT(*) AS confirmed_count
            FROM admission_records
            GROUP BY document_id
        ) cf ON cf.document_id = sd.id
        WHERE sd.id = {_ph()}
    """
    conn = get_conn()
    row = _fetchone(conn, sql, (doc_id,))
    conn.close()
    if row and row.get("avg_confidence") is not None:
        row["avg_confidence"] = float(row["avg_confidence"] or 0)
    return row


def get_document_file(doc_id: int) -> dict | None:
    conn = get_conn()
    row = _fetchone(
        conn,
        f"SELECT id AS doc_id, file_name AS filename, file_path FROM source_documents WHERE id = {_ph()}",
        (doc_id,),
    )
    conn.close()
    return row


if __name__ == "__main__":
    init_db()
