"""
admissions_v2 database layer.
Supports PostgreSQL in production and SQLite in local development.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib.parse import quote

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
    return Path(__file__).resolve().parent.parent / "database" / "admissions_v2.db"


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
            decoded[flag] = int(decoded[flag])
    if decoded.get("confidence") is not None:
        decoded["confidence"] = float(decoded["confidence"] or 0)
    return decoded


_SCHEMA_PG = """
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
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT,
    admission_year TEXT,
    field_name TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    page_number INTEGER,
    editor TEXT DEFAULT 'human_review',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS')
);
CREATE INDEX IF NOT EXISTS idx_stg_doc ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac ON admission_records(faculty);
CREATE INDEX IF NOT EXISTS idx_corr_doc ON correction_events(document_id);
CREATE INDEX IF NOT EXISTS idx_corr_field ON correction_events(field_name);
"""

_SCHEMA_SQLITE = """
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
CREATE INDEX IF NOT EXISTS idx_stg_doc ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac ON admission_records(faculty);
CREATE INDEX IF NOT EXISTS idx_corr_doc ON correction_events(document_id);
CREATE INDEX IF NOT EXISTS idx_corr_field ON correction_events(field_name);
"""

_STAGING_MIGRATION_COLUMNS = {
    "field_confidence": "TEXT DEFAULT '{}'",
    "field_evidence": "TEXT DEFAULT '{}'",
    "risk_level": "TEXT DEFAULT 'medium'",
    "manual_modified_fields": "TEXT DEFAULT '[]'",
    "is_reviewed": "INTEGER DEFAULT 0",
    "reviewed_at": "TEXT",
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


def init_db() -> None:
    conn = get_conn()
    if _pg():
        for stmt in [part.strip() for part in _SCHEMA_PG.split(";") if part.strip()]:
            _execute(conn, stmt)
    else:
        conn.executescript(_SCHEMA_SQLITE)
    _ensure_staging_columns(conn)
    conn.commit()
    conn.close()
    runtime = get_db_runtime()
    print("DB initialised (PostgreSQL)" if runtime.mode == "postgres" else "DB initialised (SQLite)")
    if runtime.warning:
        print(f"DB warning: {runtime.warning}")


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
        cur = _execute(
            conn,
            f"DELETE FROM admission_records WHERE document_id={_ph()} OR source_staging_id IN ({placeholders})",
            (doc_id, *staging_ids),
        )
        deleted_records = max(int(cur.rowcount or 0), 0)
    else:
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
    sql = (
        "SELECT id,university,admission_year,faculty,department,"
        "admission_period,application_period,deadline_rule,eju_session,eju_japanese,english_requirement,"
        "screening_method,result_date,prefecture,campus "
        f"FROM admission_records {where} ORDER BY id DESC LIMIT {_ph()} OFFSET {_ph()}"
    )
    conn = get_conn()
    rows = _fetchall(conn, sql, params)
    conn.close()
    return rows


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


if __name__ == "__main__":
    init_db()
