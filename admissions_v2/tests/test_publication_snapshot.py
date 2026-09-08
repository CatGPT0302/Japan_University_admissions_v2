import importlib
import json

import pytest


@pytest.fixture
def database(tmp_path, monkeypatch):
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "snapshot.db"))
    monkeypatch.setenv("ADMISSIONS_REQUIRE_HUMAN_REVIEW", "1")
    for name in ("DATABASE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL",
                 "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
        monkeypatch.delenv(name, raising=False)
    db = importlib.reload(importlib.import_module("scripts.db"))
    db.init_db()
    return db


def seed(db):
    doc = db.create_source_document("Example", "original.pdf", "/unused.pdf",
                                    "https://example.edu/original.pdf", "2027")
    sid = db.insert_staging_record(doc, 1, {
        "university": "Example", "admission_year": "2027", "faculty": "Science",
        "department": "Physics", "eju_math": "Course 2", "risk_level": "high",
        "field_evidence": {"eju_math": {"page": 3, "text": "Original quotation"}},
        "is_reviewed": 1, "needs_review": 0,
    })
    return doc, sid


@pytest.mark.parametrize("batch", [False, True])
def test_publication_freezes_source_and_evidence(database, batch):
    db = database
    doc, sid = seed(db)
    if batch:
        assert db.confirm_all_by_doc(doc)["written"] == 1
        program = db.get_public_programs(include_quality=True)[0]
    else:
        pid = db.confirm_staging_record(sid)
        program = db.get_public_program(pid, include_quality=True)
    conn = db.get_conn()
    snapshot = dict(conn.execute("SELECT * FROM admission_records").fetchone())
    conn.execute("UPDATE source_documents SET file_name=?, pdf_url=? WHERE id=?",
                 ("changed.pdf", "https://example.edu/changed.pdf", doc))
    conn.execute("UPDATE admission_records_staging SET eju_math=?, field_evidence=?, risk_level=? WHERE id=?",
                 ("Course 1", "{}", "low", sid))
    conn.commit()
    conn.close()
    assert db.get_public_program(program["id"], include_quality=True) == program
    assert db.get_public_programs(include_quality=True) == [program]
    assert program["source_document"]["file_name"] == "original.pdf"
    assert program["source_document"]["pdf_url"] == "https://example.edu/original.pdf"
    assert json.loads(snapshot["publication_evidence"])["eju_math"]["page"] == 3
    db.init_db()
    conn = db.get_conn()
    assert conn.execute("SELECT publication_evidence FROM admission_records").fetchone()[0] == snapshot["publication_evidence"]
    conn.close()


def test_edit_keeps_original_quote_and_accepts_explicit_evidence(database):
    db = database
    _, sid = seed(db)
    original = db.get_staging_record(sid)["field_evidence"]["eju_math"]
    changed = db.update_staging_record(sid, {"eju_math": "Corrected requirement"})
    assert changed["field_evidence"]["eju_math"] == original
    replacement = {"eju_math": {"page": 4, "text": "Correct supporting quotation"}}
    changed = db.update_staging_record(sid, {"field_evidence": replacement})
    assert changed["field_evidence"]["eju_math"] == replacement["eju_math"]


def test_unreviewed_record_cannot_create_snapshot(database):
    db = database
    doc, sid = seed(db)
    db.update_staging_record(sid, {"is_reviewed": 0})
    assert db.confirm_staging_record(sid) == 0
    assert db.confirm_all_by_doc(doc)["written"] == 0
    assert db.get_public_programs() == []
