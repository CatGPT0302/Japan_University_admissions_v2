"""Synthetic API acceptance only; not a claim of real human review."""
import os
from pathlib import Path
import subprocess
import sys


def test_review_confirm_query_and_export_roundtrip(tmp_path):
    code = r'''
import os, sys
from pathlib import Path
from io import BytesIO, StringIO
import csv
from scripts.local_demo import demo_environment
env = demo_environment(Path(sys.argv[1]), dict(os.environ))
env.update(OWNER_EMAIL="synthetic@example.com", OWNER_PASSWORD="synthetic-test-password")
os.environ.clear()
os.environ.update(env)
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from scripts import api, db
client = TestClient(api.app)
assert client.get("/records").status_code == 401
assert client.post("/auth/login", json={"email": env["OWNER_EMAIL"], "password": env["OWNER_PASSWORD"]}).status_code == 200
doc = db.create_source_document("Synthetic Test University", "synthetic.pdf", admission_year="2027")
selection = "物理・化学・生物から2科目"
row = {"university": "Synthetic Test University", "admission_year": "2027",
       "faculty": "Test Faculty", "department": "Test Department",
       "application_period": "2026-10-13 - 2026-10-20", "deadline_rule": "必着",
       "eju_session": "2026年第1回", "eju_japanese": "必須", "eju_general": "不要",
       "eju_math": "コース2", "eju_physics": selection, "eju_chemistry": selection,
       "eju_biology": selection, "english_requirement": "TOEFL required (synthetic)",
       "screening_method": "面接", "screening_schedule": "2026-10-30",
       "result_date": "2026-11-30", "enrollment_period": "2026-12-14 - 2026-12-25",
       "eligibility": "Synthetic qualification", "required_documents": "Synthetic documents",
       "evidence": "Synthetic test data, not actual university requirements",
       "field_evidence": {"eligibility": {"text": "Synthetic evidence", "page": 1}},
       "confidence": 0.5, "needs_review": 1, "is_reviewed": 0, "risk_level": "high"}
record = db.insert_staging_record(doc, 1, row)
assert client.get("/records").json() == []
assert client.get("/export/excel").status_code == 404
assert client.get("/export/csv").status_code == 404
assert client.post(f"/confirm/{doc}").status_code == 409
saved = client.patch(f"/staging/{record}", json={"data": {"campus": "Synthetic campus"}})
assert saved.status_code == 200, saved.text
again = client.get(f"/staging/{doc}").json()[0]
assert again["field_evidence"]["eligibility"] == row["field_evidence"]["eligibility"]
assert again["required_documents"] == row["required_documents"]
assert again["is_reviewed"] == 0
# Simulate the review action on synthetic data, never on the real demo records.
reviewed = client.patch(f"/staging/{record}", json={"data": {"is_reviewed": 1, "needs_review": 0}})
assert reviewed.status_code == 200, reviewed.text
confirmed = client.post(f"/confirm/{doc}")
assert confirmed.status_code == 200, confirmed.text
assert confirmed.json()["confirmed"] == 1
assert client.post(f"/confirm/{doc}").json()["confirmed"] == 0
params = {"university": row["university"], "year": 2027}
records = client.get("/records", params=params).json()
assert len(records) == 1
for key in ("eju_math", "eju_physics", "eju_chemistry", "eju_biology", "eligibility", "required_documents", "evidence"):
    assert records[0][key] == row[key], (key, records[0].get(key))
assert client.get("/records", params={"year": 2028}).json() == []
export = client.get("/export/excel", params=params)
assert export.status_code == 200, export.text if export.status_code != 200 else ""
book = load_workbook(BytesIO(export.content), read_only=True)
cells = [str(value) for sheet in book for values in sheet.iter_rows(values_only=True) for value in values if value is not None]
assert any(selection in value for value in cells), cells
assert any("コース2" in value for value in cells), cells
book.close()
export = client.get("/export/csv", params=params)
assert export.status_code == 200, export.text
rows = list(csv.reader(StringIO(export.content.decode("utf-8-sig"))))
assert len(rows) == 2, rows
assert any(selection in value for value in rows[1]), rows
print("Synthetic review/query/Excel/CSV roundtrip passed")
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1], env=dict(os.environ),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
