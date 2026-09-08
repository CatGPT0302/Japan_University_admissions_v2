"""Provider-neutral, atomic imports into the configured application's draft DB."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts import db
from scripts.import_demo_data import validate_package


class IngestionConflict(ValueError):
    pass


def _ensure_table(conn):
    db._execute(conn, """CREATE TABLE IF NOT EXISTS extraction_ingestions (
        id TEXT PRIMARY KEY, document_id INTEGER, source_sha256 TEXT NOT NULL,
        record_count INTEGER NOT NULL, created_at TEXT NOT NULL
    )""")


def _receipt(row, status="imported"):
    return {
        "ingestion_id": row["id"], "status": status,
        "doc_id": row["document_id"], "records": row["record_count"],
        "source_sha256": row["source_sha256"],
        "quality_status": "needs_human_review", "next_step": "human_review",
        "confirmed_records_written": 0,
        "preview_url": f"/#/review?doc_id={row['document_id']}",
    }


def get_ingestion(ingestion_id):
    conn = db.get_conn()
    try:
        _ensure_table(conn)
        row = db._fetchone(conn, f"SELECT * FROM extraction_ingestions WHERE id={db._ph()}", (ingestion_id,))
        conn.commit()
        return _receipt(row) if row else None
    finally:
        conn.close()


def ingest(package: dict, source: Path, upload_root: Path) -> dict:
    rows = validate_package(package, source)
    fingerprint = hashlib.sha256(json.dumps(package, ensure_ascii=False,
                                            sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    document = package["document"]
    filename = f"ingestion-{fingerprint}.pdf"
    target = upload_root / filename
    upload_root.mkdir(parents=True, exist_ok=True)
    conn = db.get_conn()
    created_file = False
    try:
        _ensure_table(conn)
        # A unique receipt claims the request inside the same document transaction.
        db._execute(conn, f"INSERT INTO extraction_ingestions "
                    f"(id,source_sha256,record_count,created_at) VALUES ({db._phn(4)}) "
                    "ON CONFLICT(id) DO NOTHING",
                    (fingerprint, document["sha256"], len(rows), db._now()))
        receipt = db._fetchone(conn, f"SELECT * FROM extraction_ingestions WHERE id={db._ph()}", (fingerprint,))
        if receipt["document_id"] is not None:
            existing = db._fetchone(conn, f"SELECT id FROM source_documents WHERE id={db._ph()}",
                                    (receipt["document_id"],))
            if not existing or not target.is_file():
                raise IngestionConflict("Previously imported source was removed; restore it before retrying")
            if hashlib.sha256(target.read_bytes()).hexdigest() != document["sha256"]:
                raise IngestionConflict("Stored source hash mismatch")
            conn.commit()
            return _receipt(receipt, "already_imported")
        content = source.read_bytes()
        if target.exists():
            if hashlib.sha256(target.read_bytes()).hexdigest() != document["sha256"]:
                raise IngestionConflict("Stored source hash mismatch")
        else:
            with target.open("xb") as output:
                created_file = True
                output.write(content)
        doc_id = db.create_source_document(document["university"], filename, str(target),
                                           document["source_url"], document["year"], connection=conn)
        for row in rows:
            db.insert_staging_record(doc_id, row["field_evidence"]["faculty"]["page"], row, connection=conn)
        db._execute(conn, f"UPDATE source_documents SET status='extracted' WHERE id={db._ph()}", (doc_id,))
        db._execute(conn, f"UPDATE extraction_ingestions SET document_id={db._ph()} WHERE id={db._ph()}",
                    (doc_id, fingerprint))
        conn.commit()
        return _receipt({**receipt, "document_id": doc_id})
    except Exception:
        if created_file:
            target.unlink(missing_ok=True)
        conn.rollback()
        raise
    finally:
        conn.close()
