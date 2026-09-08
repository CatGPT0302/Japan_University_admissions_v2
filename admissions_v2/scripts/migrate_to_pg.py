"""
Migrate local SQLite data to Railway PostgreSQL.

Usage:
    DATABASE_URL=<pg_url> python scripts/migrate_to_pg.py [path/to/admissions_v2.db]

The script:
1. Reads all rows from SQLite (source_documents, admission_records_staging, admission_records)
2. Initialises the PostgreSQL schema via db.init_db()
3. Inserts all rows with explicit IDs to preserve foreign-key relationships
4. Resets PostgreSQL SERIAL sequences to max(id)+1
5. Prints a verification summary
"""
from __future__ import annotations
import os, sys, sqlite3
from pathlib import Path

DEFAULT_SQLITE = Path(__file__).resolve().parent.parent / "database" / "admissions_v2.db"

def main():
    sqlite_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SQLITE
    if not sqlite_path.exists():
        sys.exit(f"SQLite DB not found: {sqlite_path}")

    db_url = os.environ.get("DATABASE_URL", "")
    if not db_url or not db_url.startswith("postgres"):
        sys.exit("DATABASE_URL must be a PostgreSQL URL (postgres://...)")

    import psycopg2, psycopg2.extras

    # ── 1. read SQLite ────────────────────────────────────────────────────────
    src = sqlite3.connect(str(sqlite_path))
    src.row_factory = sqlite3.Row

    def fetch(table):
        return [dict(r) for r in src.execute(f"SELECT * FROM {table} ORDER BY id").fetchall()]

    docs    = fetch("source_documents")
    staging = fetch("admission_records_staging")
    records = fetch("admission_records")
    src.close()

    print(f"SQLite  → source_documents: {len(docs)}, staging: {len(staging)}, records: {len(records)}")

    # ── 2. connect PostgreSQL ─────────────────────────────────────────────────
    pg_url = db_url.replace("postgres://", "postgresql://", 1)
    conn = psycopg2.connect(pg_url, cursor_factory=psycopg2.extras.RealDictCursor)
    cur = conn.cursor()

    # ── 3. init schema ────────────────────────────────────────────────────────
    os.environ["DATABASE_URL"] = db_url
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.db import _SCHEMA_PG
    for stmt in _SCHEMA_PG.split(";"):
        stmt = stmt.strip()
        if stmt:
            cur.execute(stmt)
    conn.commit()
    print("Schema initialised.")

    # ── 4. insert with explicit IDs ───────────────────────────────────────────
    def cols_placeholders(row: dict):
        cols = ", ".join(row.keys())
        phs  = ", ".join("%s" for _ in row)
        return cols, phs

    def insert_all(table, rows):
        if not rows:
            return
        cols, phs = cols_placeholders(rows[0])
        sql = f"INSERT INTO {table} ({cols}) VALUES ({phs}) ON CONFLICT (id) DO NOTHING"
        cur.executemany(sql, [tuple(r.values()) for r in rows])
        conn.commit()

    insert_all("source_documents", docs)
    insert_all("admission_records_staging", staging)
    insert_all("admission_records", records)
    print("Rows inserted.")

    # ── 5. reset SERIAL sequences ─────────────────────────────────────────────
    for table in ("source_documents", "admission_records_staging", "admission_records"):
        cur.execute(f"SELECT MAX(id) FROM {table}")
        max_id = (cur.fetchone() or {}).get("max", 0) or 0
        seq = f"{table}_id_seq"
        cur.execute(f"SELECT setval('{seq}', %s)", (max(max_id, 1),))
    conn.commit()
    print("Sequences reset.")

    # ── 6. verify ────────────────────────────────────────────────────────────
    def pg_count(table):
        cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
        return (cur.fetchone() or {}).get("c", 0)

    pd, ps, pr = pg_count("source_documents"), pg_count("admission_records_staging"), pg_count("admission_records")
    print(f"PostgreSQL → source_documents: {pd}, staging: {ps}, records: {pr}")

    ok = pd == len(docs) and ps == len(staging) and pr == len(records)
    print("Migration", "SUCCESS" if ok else "MISMATCH -- check above counts")
    conn.close()

if __name__ == "__main__":
    main()
