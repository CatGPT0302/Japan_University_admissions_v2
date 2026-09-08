import copy
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import sys

import pypdfium2 as pdfium
import pytest

from scripts.import_demo_data import REQUIRED, import_package, validate_package


@pytest.fixture
def sample(tmp_path):
    source = tmp_path / "sample.pdf"
    with pdfium.PdfDocument.new() as pdf:
        page = pdf.new_page(300, 300)
        page.close()
        pdf.save(source)
    record = {key: "test" for key in REQUIRED}
    record.update(university="Example University", admission_year="2027",
                  eju_physics="物理・化学・生物から2科目", eju_math="コース2",
                  field_evidence={key: {"page": 1, "text": "Synthetic test evidence"} for key in REQUIRED},
                  warnings=["Synthetic fixture, not admissions information"])
    package = {"document": {"university": "Example University", "year": "2027",
                            "source_url": "https://example.com/sample.pdf",
                            "sha256": hashlib.sha256(source.read_bytes()).hexdigest()},
               "records": [record]}
    return package, source


def test_validation_preserves_eju_and_requires_review(sample):
    package, source = sample
    row = validate_package(package, source)[0]
    assert row["eju_physics"] == "物理・化学・生物から2科目"
    assert row["eju_math"] == "コース2"
    assert row["is_reviewed"] == 0
    assert row["needs_review"] == 1
    assert row["risk_level"] == "high"
    assert import_package(package, source)["status"] == "validated"


@pytest.mark.parametrize("fault", ["hash", "page", "missing", "reviewed", "duplicate", "identity"])
def test_invalid_packages_are_rejected(sample, fault):
    package, source = sample
    package = copy.deepcopy(package)
    record = package["records"][0]
    if fault == "hash":
        package["document"]["sha256"] = "0" * 64
    elif fault == "page":
        record["field_evidence"]["eju_math"]["page"] = 2
    elif fault == "missing":
        del record["field_evidence"]["eju_math"]
    elif fault == "reviewed":
        record["is_reviewed"] = 1
    elif fault == "duplicate":
        package["records"].append(copy.deepcopy(record))
    else:
        record["admission_year"] = "2028"
    with pytest.raises(ValueError):
        validate_package(package, source)


def test_apply_writes_only_staging_and_reimport_is_idempotent(sample, tmp_path):
    package, source = sample
    input_path = tmp_path / "package.json"
    input_path.write_text(json.dumps(package), encoding="utf-8")
    demo = tmp_path / "isolated"
    code = """
import json, sys
from pathlib import Path
from scripts import import_demo_data as importer
importer.DEFAULT_DEMO_ROOT = Path(sys.argv[1])
print(json.dumps(importer.import_package(json.loads(Path(sys.argv[2]).read_text()), Path(sys.argv[3]), apply=True)))
"""
    env = {**os.environ, "DATABASE_URL": "postgresql://must-not-connect.invalid/private"}
    def run():
        result = subprocess.run([sys.executable, "-c", code, str(demo), str(input_path), str(source)],
                                cwd=Path(__file__).resolve().parents[1], env=env,
                                text=True, capture_output=True, check=True)
        return json.loads(result.stdout.strip().splitlines()[-1])
    first = run()
    second = run()
    assert first["status"] == "imported"
    assert second["status"] == "already_imported"
    assert first["doc_id"] == second["doc_id"]
    with sqlite3.connect(demo / "data/admissions.db") as conn:
        assert conn.execute("SELECT COUNT(*) FROM admission_records").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0] == 1
        assert conn.execute("SELECT needs_review,is_reviewed,risk_level FROM admission_records_staging").fetchall() == [(1, 0, "high")]
