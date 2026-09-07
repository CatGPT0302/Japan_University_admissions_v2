"""Real SQLite transaction and API tests; never use the user's database."""
import copy
import hashlib
import json

import pypdfium2 as pdfium
import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient

from scripts import db, ingestion
from scripts.import_demo_data import REQUIRED
from scripts.ingestion_api import register_ingestion_routes


@pytest.fixture
def sample(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DATABASE_URL", "")
    monkeypatch.setattr(db, "SQLITE_PATH", tmp_path / "test.db")
    db.init_db()
    source = tmp_path / "source.pdf"
    with pdfium.PdfDocument.new() as pdf:
        page = pdf.new_page(300, 300)
        page.close()
        pdf.save(source)
    row = {key: "Synthetic test only" for key in REQUIRED}
    row.update(university="Test University", admission_year="2027",
               field_evidence={key: {"page": 1, "text": "Synthetic evidence"} for key in REQUIRED})
    package = {"document": {"university": "Test University", "year": "2027",
                            "source_url": "https://example.org/source.pdf",
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}, "records": [row]}
    return package, source, tmp_path / "uploads"


def counts():
    conn = db.get_conn()
    try:
        return [conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in ("source_documents", "admission_records_staging", "admission_records")]
    finally:
        conn.close()


def test_idempotence_and_human_edit_preservation(sample):
    package, source, uploads = sample
    first = ingestion.ingest(package, source, uploads)
    row = db.get_staging_records(first["doc_id"])[0]
    db.update_staging_record(row["id"], {"campus": "Human edit"})
    again = ingestion.ingest(package, source, uploads)
    assert again["status"] == "already_imported"
    assert again["doc_id"] == first["doc_id"]
    assert db.get_staging_record(row["id"])["campus"] == "Human edit"
    assert counts() == [1, 1, 0]
    assert ingestion.get_ingestion(first["ingestion_id"])["next_step"] == "human_review"


def test_reextraction_creates_separate_draft(sample):
    package, source, uploads = sample
    first = ingestion.ingest(package, source, uploads)
    changed = copy.deepcopy(package)
    changed["records"][0]["campus"] = "Updated extraction"
    second = ingestion.ingest(changed, source, uploads)
    assert first["doc_id"] != second["doc_id"]
    assert counts() == [2, 2, 0]
    assert all(row["is_reviewed"] == 0 for row in db.get_staging_records(second["doc_id"]))


def test_transaction_failure_rolls_back_all_rows_and_file(sample, monkeypatch):
    package, source, uploads = sample
    second = copy.deepcopy(package["records"][0])
    second["department"] = "Second program"
    package["records"].append(second)
    original = db.insert_staging_record
    calls = 0
    def fail_second(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("Synthetic write failure")
        return original(*args, **kwargs)
    monkeypatch.setattr(db, "insert_staging_record", fail_second)
    with pytest.raises(RuntimeError):
        ingestion.ingest(package, source, uploads)
    assert counts() == [0, 0, 0]
    assert list(uploads.iterdir()) == []
    monkeypatch.setattr(db, "insert_staging_record", original)
    assert ingestion.ingest(package, source, uploads)["records"] == 2


def test_invalid_source_writes_nothing(sample):
    package, source, uploads = sample
    package["document"]["sha256"] = "0" * 64
    with pytest.raises(ValueError, match="sha256"):
        ingestion.ingest(package, source, uploads)
    assert counts() == [0, 0, 0]


def test_authenticated_api_and_temp_cleanup(sample, monkeypatch):
    package, source, uploads = sample
    app = FastAPI()
    def deny(request):
        raise HTTPException(401, "Sign in")
    register_ingestion_routes(app, deny, uploads)
    monkeypatch.setenv("ADMISSIONS_INGEST_TOKEN", "synthetic-token")
    client = TestClient(app)
    def post(token="", payload=None):
        return client.post("/ingestions", data={"package": json.dumps(payload or package)},
                           files={"file": ("source.pdf", source.read_bytes(), "application/pdf")},
                           headers={"Authorization": f"Bearer {token}"})
    assert post().status_code == 401
    response = post("synthetic-token")
    assert response.status_code == 200, response.text
    receipt = response.json()
    assert receipt["quality_status"] == "needs_human_review"
    assert receipt["confirmed_records_written"] == 0
    assert client.get("/ingestions/" + receipt["ingestion_id"]).status_code == 401
    assert client.get("/ingestions/" + receipt["ingestion_id"],
                      headers={"Authorization": "Bearer synthetic-token"}).status_code == 200
    assert post("synthetic-token").json()["status"] == "already_imported"
    invalid = copy.deepcopy(package)
    invalid["records"][0]["is_reviewed"] = 1
    assert post("synthetic-token", invalid).status_code == 422
    assert list((uploads.parent / "work" / "ingestions").iterdir()) == []
    assert counts() == [1, 1, 0]
