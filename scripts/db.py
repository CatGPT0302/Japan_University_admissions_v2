"""
admissions_v2 database — PostgreSQL (production) / SQLite (local dev).
Auto-switches based on DATABASE_URL environment variable.
"""
from __future__ import annotations
import json, os, sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

DATABASE_URL = os.environ.get("DATABASE_URL", "")

def _pg() -> bool:
    return bool(DATABASE_URL and DATABASE_URL.startswith("postgres"))

def _ph() -> str:
    return "%s" if _pg() else "?"

def _phn(n: int) -> str:
    p = _ph()
    return ",".join(p for _ in range(n))

def _now() -> str:
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")

def get_conn():
    if _pg():
        import psycopg2, psycopg2.extras
        url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
        return psycopg2.connect(url, cursor_factory=psycopg2.extras.RealDictCursor)
    DB = Path(__file__).resolve().parent.parent / "database" / "admissions_v2.db"
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn

def _fetchall(conn, sql, params=()):
    if _pg():
        cur = conn.cursor(); cur.execute(sql, params)
        return [dict(r) for r in cur.fetchall()]
    return [dict(r) for r in conn.execute(sql, params).fetchall()]

def _fetchone(conn, sql, params=()):
    if _pg():
        cur = conn.cursor(); cur.execute(sql, params)
        r = cur.fetchone(); return dict(r) if r else None
    r = conn.execute(sql, params).fetchone(); return dict(r) if r else None

def _execute(conn, sql, params=()):
    if _pg():
        cur = conn.cursor(); cur.execute(sql, params); return cur
    return conn.execute(sql, params)

def _lastrowid(cur) -> int:
    if _pg():
        r = cur.fetchone()
        if r is None: return 0
        v = list(r.values())[0] if hasattr(r, 'values') else r[0]
        return int(v)
    return cur.lastrowid

_SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS source_documents (
    id SERIAL PRIMARY KEY, university TEXT NOT NULL, pdf_url TEXT,
    file_name TEXT NOT NULL, file_path TEXT, admission_year TEXT,
    status TEXT DEFAULT 'uploaded',
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'));
CREATE TABLE IF NOT EXISTS document_pages (
    id SERIAL PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER NOT NULL, image_path TEXT, status TEXT DEFAULT 'pending',
    raw_llm_json TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'));
CREATE TABLE IF NOT EXISTS admission_records_staging (
    id SERIAL PRIMARY KEY, document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER, university TEXT, admission_year TEXT, admission_period TEXT,
    faculty TEXT, department TEXT, application_period TEXT, deadline_rule TEXT,
    eju_session TEXT, eju_japanese TEXT, eju_general TEXT, eju_math TEXT,
    eju_physics TEXT, eju_chemistry TEXT, eju_biology TEXT,
    english_requirement TEXT, screening_method TEXT, screening_schedule TEXT,
    result_date TEXT, enrollment_period TEXT, prefecture TEXT, campus TEXT,
    confidence REAL DEFAULT 0.0, needs_review INTEGER DEFAULT 1,
    warnings_json TEXT DEFAULT '[]', is_confirmed INTEGER DEFAULT 0,
    raw_llm_json TEXT,
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'));
CREATE TABLE IF NOT EXISTS admission_records (
    id SERIAL PRIMARY KEY,
    source_staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT, pdf_url TEXT, admission_year TEXT, admission_period TEXT,
    faculty TEXT, department TEXT, application_period TEXT, deadline_rule TEXT,
    eju_session TEXT, eju_japanese TEXT, eju_general TEXT, eju_math TEXT,
    eju_physics TEXT, eju_chemistry TEXT, eju_biology TEXT,
    english_requirement TEXT, screening_method TEXT, screening_schedule TEXT,
    result_date TEXT, enrollment_period TEXT, prefecture TEXT, campus TEXT,
    confirmed_by TEXT DEFAULT 'human',
    confirmed_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    created_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'),
    updated_at TEXT DEFAULT to_char(now(),'YYYY-MM-DD"T"HH24:MI:SS'));
CREATE INDEX IF NOT EXISTS idx_stg_doc  ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev  ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac  ON admission_records(faculty);
"""

_SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS source_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT, university TEXT NOT NULL, pdf_url TEXT,
    file_name TEXT NOT NULL, file_path TEXT, admission_year TEXT,
    status TEXT DEFAULT 'uploaded',
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS document_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER NOT NULL, image_path TEXT, status TEXT DEFAULT 'pending',
    raw_llm_json TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS admission_records_staging (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    document_id INTEGER NOT NULL REFERENCES source_documents(id),
    page_number INTEGER, university TEXT, admission_year TEXT, admission_period TEXT,
    faculty TEXT, department TEXT, application_period TEXT, deadline_rule TEXT,
    eju_session TEXT, eju_japanese TEXT, eju_general TEXT, eju_math TEXT,
    eju_physics TEXT, eju_chemistry TEXT, eju_biology TEXT,
    english_requirement TEXT, screening_method TEXT, screening_schedule TEXT,
    result_date TEXT, enrollment_period TEXT, prefecture TEXT, campus TEXT,
    confidence REAL DEFAULT 0.0, needs_review INTEGER DEFAULT 1,
    warnings_json TEXT DEFAULT '[]', is_confirmed INTEGER DEFAULT 0,
    raw_llm_json TEXT,
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')));
CREATE TABLE IF NOT EXISTS admission_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_staging_id INTEGER REFERENCES admission_records_staging(id),
    document_id INTEGER REFERENCES source_documents(id),
    university TEXT, pdf_url TEXT, admission_year TEXT, admission_period TEXT,
    faculty TEXT, department TEXT, application_period TEXT, deadline_rule TEXT,
    eju_session TEXT, eju_japanese TEXT, eju_general TEXT, eju_math TEXT,
    eju_physics TEXT, eju_chemistry TEXT, eju_biology TEXT,
    english_requirement TEXT, screening_method TEXT, screening_schedule TEXT,
    result_date TEXT, enrollment_period TEXT, prefecture TEXT, campus TEXT,
    confirmed_by TEXT DEFAULT 'human',
    confirmed_at TEXT DEFAULT (datetime('now','localtime')),
    created_at TEXT DEFAULT (datetime('now','localtime')),
    updated_at TEXT DEFAULT (datetime('now','localtime')));
CREATE INDEX IF NOT EXISTS idx_stg_doc  ON admission_records_staging(document_id);
CREATE INDEX IF NOT EXISTS idx_stg_rev  ON admission_records_staging(needs_review);
CREATE INDEX IF NOT EXISTS idx_rec_univ ON admission_records(university);
CREATE INDEX IF NOT EXISTS idx_rec_fac  ON admission_records(faculty);
"""

def init_db() -> None:
    conn = get_conn()
    if _pg():
        cur = conn.cursor()
        for stmt in _SCHEMA_PG.split(";"):
            stmt = stmt.strip()
            if stmt: cur.execute(stmt)
        conn.commit()
        print("DB initialised (PostgreSQL)")
    else:
        conn.executescript(_SCHEMA_SQLITE)
        conn.commit()
        print("DB initialised (SQLite)")
    conn.close()

def create_source_document(university, file_name, file_path="", pdf_url="", admission_year="") -> int:
    ph = _ph()
    sql = f"INSERT INTO source_documents (university,file_name,file_path,pdf_url,admission_year) VALUES ({ph},{ph},{ph},{ph},{ph})"
    if _pg(): sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, (university, file_name, file_path, pdf_url, admission_year))
    doc_id = _lastrowid(cur)
    conn.commit(); conn.close()
    return doc_id

def update_source_document(doc_id, **kwargs):
    if not kwargs: return
    kwargs["updated_at"] = _now()
    ph = _ph()
    sets = ", ".join(f"{k}={ph}" for k in kwargs)
    conn = get_conn()
    _execute(conn, f"UPDATE source_documents SET {sets} WHERE id={ph}", (*kwargs.values(), doc_id))
    conn.commit(); conn.close()

def insert_document_page(doc_id, page_number, image_path) -> int:
    ph = _ph()
    sql = f"INSERT INTO document_pages (document_id,page_number,image_path,status) VALUES ({ph},{ph},{ph},'pending')"
    if _pg(): sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, (doc_id, page_number, image_path))
    page_id = _lastrowid(cur)
    conn.commit(); conn.close()
    return page_id

def update_document_page(page_id, status, raw_llm_json=""):
    ph = _ph()
    conn = get_conn()
    _execute(conn, f"UPDATE document_pages SET status={ph},raw_llm_json={ph} WHERE id={ph}", (status, raw_llm_json, page_id))
    conn.commit(); conn.close()

def insert_staging_record(doc_id, page_number, record) -> int:
    fields = ["document_id","page_number","university","admission_year","admission_period",
              "faculty","department","application_period","deadline_rule",
              "eju_session","eju_japanese","eju_general","eju_math",
              "eju_physics","eju_chemistry","eju_biology","english_requirement",
              "screening_method","screening_schedule","result_date",
              "enrollment_period","prefecture","campus",
              "confidence","needs_review","warnings_json","raw_llm_json"]
    values: list[Any] = [doc_id, page_number]
    for f in fields[2:]:
        v = record.get(f, "")
        if f == "warnings_json" and isinstance(v, list): v = json.dumps(v, ensure_ascii=False)
        if f == "raw_llm_json" and isinstance(v, dict):  v = json.dumps(v, ensure_ascii=False)
        values.append(v)
    sql = f"INSERT INTO admission_records_staging ({','.join(fields)}) VALUES ({_phn(len(fields))})"
    if _pg(): sql += " RETURNING id"
    conn = get_conn()
    cur = _execute(conn, sql, values)
    row_id = _lastrowid(cur)
    conn.commit(); conn.close()
    return row_id

def get_staging_records(doc_id) -> list[dict]:
    ph = _ph()
    conn = get_conn()
    rows = _fetchall(conn, f"SELECT * FROM admission_records_staging WHERE document_id={ph} ORDER BY id", (doc_id,))
    conn.close(); return rows

def get_staging_record(staging_id) -> dict | None:
    ph = _ph()
    conn = get_conn()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={ph}", (staging_id,))
    conn.close(); return row

def update_staging_record(staging_id, data) -> dict | None:
    if not data: return get_staging_record(staging_id)
    allowed = {"document_id","page_number","university","admission_year","admission_period",
               "faculty","department","application_period","deadline_rule",
               "eju_session","eju_japanese","eju_general","eju_math",
               "eju_physics","eju_chemistry","eju_biology","english_requirement",
               "screening_method","screening_schedule","result_date","enrollment_period",
               "prefecture","campus","confidence","needs_review","warnings_json",
               "raw_llm_json","is_confirmed"}
    fields = {k: v for k, v in data.items() if k in allowed}
    if not fields: return get_staging_record(staging_id)
    if isinstance(fields.get("warnings_json"), list):
        fields["warnings_json"] = json.dumps(fields["warnings_json"], ensure_ascii=False)
    if isinstance(fields.get("raw_llm_json"), dict):
        fields["raw_llm_json"] = json.dumps(fields["raw_llm_json"], ensure_ascii=False)
    fields["updated_at"] = _now()
    ph = _ph()
    sets = ", ".join(f"{k}={ph}" for k in fields)
    conn = get_conn()
    _execute(conn, f"UPDATE admission_records_staging SET {sets} WHERE id={ph}", (*fields.values(), staging_id))
    conn.commit()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={ph}", (staging_id,))
    conn.close(); return row

def delete_staging_record(staging_id) -> bool:
    ph = _ph()
    conn = get_conn()
    _execute(conn, f"DELETE FROM admission_records_staging WHERE id={ph}", (staging_id,))
    conn.commit(); conn.close(); return True

def _confirm_row(conn, r: dict, pdf_url="") -> int:
    doc = _fetchone(conn, f"SELECT pdf_url FROM source_documents WHERE id={_ph()}", (r["document_id"],))
    doc_url = pdf_url or (doc["pdf_url"] if doc else "")
    ph24 = _phn(24)
    sql = f"""INSERT INTO admission_records (
        source_staging_id,document_id,university,pdf_url,admission_year,admission_period,
        faculty,department,application_period,deadline_rule,
        eju_session,eju_japanese,eju_general,eju_math,eju_physics,eju_chemistry,eju_biology,
        english_requirement,screening_method,screening_schedule,
        result_date,enrollment_period,prefecture,campus) VALUES ({ph24})"""
    if _pg(): sql += " RETURNING id"
    cur = _execute(conn, sql, (
        r["id"],r["document_id"],r["university"],doc_url,r["admission_year"],r["admission_period"],
        r["faculty"],r["department"],r["application_period"],r["deadline_rule"],
        r["eju_session"],r["eju_japanese"],r["eju_general"],r["eju_math"],
        r["eju_physics"],r["eju_chemistry"],r["eju_biology"],
        r["english_requirement"],r["screening_method"],r["screening_schedule"],
        r["result_date"],r["enrollment_period"],r["prefecture"],r["campus"]))
    return _lastrowid(cur)

def confirm_staging_record(staging_id, pdf_url="") -> int:
    ph = _ph()
    conn = get_conn()
    row = _fetchone(conn, f"SELECT * FROM admission_records_staging WHERE id={ph}", (staging_id,))
    if not row: conn.close(); return 0
    new_id = _confirm_row(conn, row, pdf_url)
    _execute(conn, f"UPDATE admission_records_staging SET is_confirmed=1,updated_at={ph} WHERE id={ph}", (_now(), staging_id))
    conn.commit(); conn.close(); return new_id

def confirm_all_by_doc(doc_id, pdf_url="") -> dict:
    ph = _ph()
    conn = get_conn()
    rows = _fetchall(conn,
        f"SELECT * FROM admission_records_staging WHERE document_id={ph} ORDER BY COALESCE(confidence,0) DESC, id DESC",
        (doc_id,))
    if not rows: conn.close(); return {"processed":0,"written":0,"skipped":0}
    best: dict[tuple, dict] = {}
    for r in rows:
        key = ((r.get("university") or "").strip(),(r.get("admission_year") or "").strip(),
               (r.get("faculty") or "").strip(),(r.get("department") or "").strip())
        if key not in best or float(r.get("confidence") or 0) > float(best[key].get("confidence") or 0):
            best[key] = r
    now = _now()
    for r in rows:
        _execute(conn, f"UPDATE admission_records_staging SET is_confirmed=1,updated_at={ph} WHERE id={ph}", (now, r["id"]))
    existing = _fetchall(conn,
        f"SELECT university,admission_year,faculty,department FROM admission_records WHERE document_id={ph}", (doc_id,))
    existing_keys = {((r["university"] or "").strip(),(r["admission_year"] or "").strip(),
                      (r["faculty"] or "").strip(),(r["department"] or "").strip()) for r in existing}
    written = skipped = 0
    for key, row in best.items():
        if key in existing_keys: skipped += 1; continue
        _confirm_row(conn, row, pdf_url); written += 1
    conn.commit(); conn.close()
    return {"processed":len(rows),"written":written,"skipped":skipped}

def get_records(university=None, year=None, faculty=None, limit=100, offset=0) -> list[dict]:
    clauses, params = [], []
    ph = _ph()
    like = "ILIKE" if _pg() else "LIKE"
    if university: clauses.append(f"university {like} {ph}"); params.append(f"%{university}%")
    if year is not None: clauses.append(f"admission_year = {ph}"); params.append(str(year))
    if faculty: clauses.append(f"faculty {like} {ph}"); params.append(f"%{faculty}%")
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    params.extend([limit, offset])
    sql = f"""SELECT id,university,admission_year,faculty,department,
              admission_period,application_period,english_requirement,
              screening_method,result_date,prefecture,campus
              FROM admission_records {where} ORDER BY id DESC LIMIT {ph} OFFSET {ph}"""
    conn = get_conn()
    rows = _fetchall(conn, sql, params)
    conn.close(); return rows

def get_stats() -> dict:
    conn = get_conn()
    total   = (_fetchone(conn,"SELECT COUNT(*) AS c FROM admission_records") or {}).get("c",0)
    staging = (_fetchone(conn,"SELECT COUNT(*) AS c FROM admission_records_staging") or {}).get("c",0)
    univs   = (_fetchone(conn,"SELECT COUNT(DISTINCT university) AS c FROM admission_records WHERE TRIM(COALESCE(university,''))<>''") or {}).get("c",0)
    if _pg():
        avg = (_fetchone(conn,"SELECT ROUND(AVG(confidence)::numeric,2) AS c FROM admission_records_staging") or {}).get("c",0)
    else:
        avg = (_fetchone(conn,"SELECT ROUND(AVG(confidence),2) AS c FROM admission_records_staging") or {}).get("c",0)
    conn.close()
    return {"total_records":int(total or 0),"staging_records":int(staging or 0),
            "universities":int(univs or 0),"avg_confidence":float(avg or 0)}

def get_documents(query: str | None = None, year: str | None = None, limit: int = 100, offset: int = 0) -> list[dict]:
    clauses, params = [], []
    ph = _ph()
    like = "ILIKE" if _pg() else "LIKE"
    if query:
        clauses.append(
            f"(sd.university {like} {ph} OR sd.file_name {like} {ph} OR COALESCE(sd.pdf_url,'') {like} {ph})"
        )
        q = f"%{query}%"
        params.extend([q, q, q])
    if year:
        clauses.append(f"sd.admission_year = {ph}")
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
        LIMIT {ph} OFFSET {ph}
    """
    conn = get_conn()
    rows = _fetchall(conn, sql, params)
    conn.close()
    return rows

def get_document_summary(doc_id: int) -> dict | None:
    ph = _ph()
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
        WHERE sd.id = {ph}
    """
    conn = get_conn()
    row = _fetchone(conn, sql, (doc_id,))
    conn.close()
    if row and row.get("avg_confidence") is not None:
        row["avg_confidence"] = float(row["avg_confidence"] or 0)
    return row

if __name__ == "__main__":
    init_db()
