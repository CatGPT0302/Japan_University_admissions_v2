"""Exercise the actual database gate in a fresh isolated process."""
import os
from pathlib import Path
import subprocess
import sys


def test_demo_requires_human_review_even_for_low_risk_records(tmp_path):
    code = r'''
import os, sys
from pathlib import Path
from scripts.local_demo import demo_environment
env = demo_environment(Path(sys.argv[1]), dict(os.environ))
os.environ.clear()
os.environ.update(env)
from scripts import db
db.init_db()
doc = db.create_source_document("Synthetic test only", "test.pdf", admission_year="2027")
row = {"university": "Synthetic test only", "admission_year": "2027",
       "faculty": "Test faculty", "department": "Test department",
       "confidence": 0.99, "risk_level": "low", "needs_review": 1, "is_reviewed": 0,
       "eligibility": "Synthetic eligibility", "required_documents": "Synthetic documents",
       "field_evidence": {"eligibility": {"text": "Synthetic evidence", "page": 1}}}
record = db.insert_staging_record(doc, 1, row)
assert db.confirm_staging_record(record) == 0, "Unreviewed low-risk row was confirmed"
assert db.confirm_all_by_doc(doc)["written"] == 0, "Bulk confirmation bypassed review"
saved = db.update_staging_record(record, {"campus": "Synthetic campus"})
assert saved["field_evidence"]["eligibility"] == row["field_evidence"]["eligibility"]
assert saved["eligibility"] == row["eligibility"]
assert saved["is_reviewed"] == 0
db.update_staging_record(record, {"is_reviewed": 1})
assert db.confirm_all_by_doc(doc)["written"] == 1
assert db.confirm_all_by_doc(doc)["written"] == 0
conn = db.get_conn()
assert conn.execute("SELECT COUNT(*) FROM admission_records").fetchone()[0] == 1
conn.close()
'''
    result = subprocess.run([sys.executable, "-c", code, str(tmp_path)],
                            cwd=Path(__file__).resolve().parents[1], env=dict(os.environ),
                            text=True, capture_output=True)
    assert result.returncode == 0, result.stdout + result.stderr
