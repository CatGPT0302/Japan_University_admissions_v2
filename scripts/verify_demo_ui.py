"""Exercise browser confirmation with one synthetic row and remove it afterwards."""
import csv
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import uuid

from scripts.local_demo import DEFAULT_DEMO_ROOT, ROOT, demo_environment


def main():
    if "scripts.db" in sys.modules:
        raise RuntimeError("Run verification in a fresh process")
    env = demo_environment(DEFAULT_DEMO_ROOT, dict(os.environ))
    os.environ.clear()
    os.environ.update(env)
    from scripts import db
    from openpyxl import load_workbook

    db.init_db()
    university = "Synthetic UI Test " + uuid.uuid4().hex[:8]
    source = json.loads((ROOT / "examples/demo/fukui_2027_codex.json").read_text())["records"][0]
    row = dict(source)
    row.update(university=university, department="Synthetic department", eligibility="Synthetic qualification",
               required_documents="Synthetic documents", evidence="Synthetic test only, not admissions information",
               eju_physics="物理・化学・生物から2科目", is_reviewed=0, needs_review=1, risk_level="high",
               confidence=0, warnings_json=["Synthetic browser acceptance fixture"],
               field_evidence={"eligibility": {"text": "Synthetic qualification evidence", "page": 1}})
    doc_id = db.create_source_document(university, "synthetic-ui-test.pdf", admission_year="2027")
    try:
        db.insert_staging_record(doc_id, 1, row)
        scratch = ROOT / "runtime/work/browser-verification"
        scratch.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="admissions-ui-test-", dir=scratch) as directory:
            output = Path(directory)
            metadata = output / "fixture.json"
            metadata.write_text(json.dumps({"doc_id": doc_id, "university": university}))
            node = shutil.which("node") or str(Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node")
            subprocess.run([node, str(ROOT / "frontend/scripts/verify-demo-review.mjs"), str(metadata),
                            str(DEFAULT_DEMO_ROOT / "access.json"), directory], cwd=ROOT, check=True, timeout=120)
            with (output / "confirmed.csv").open(encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))
            assert len(rows) == 2
            assert university in rows[1]
            assert any("物理・化学・生物から2科目" in value for value in rows[1])
            book = load_workbook(output / "confirmed.xlsx", read_only=True)
            cells = [str(value) for sheet in book for row in sheet.iter_rows(values_only=True) for value in row if value is not None]
            book.close()
            assert university in cells
            assert any("物理・化学・生物から2科目" in value for value in cells)
            print("Downloaded Excel and CSV contents verified.")
    finally:
        db.delete_document(doc_id)
        assert db.get_document_summary(doc_id) is None
        print("Synthetic document and related records removed.")


if __name__ == "__main__":
    main()
