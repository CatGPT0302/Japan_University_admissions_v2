import hashlib
import json
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from scripts.demo_batch import prepare_batch, write_bundle


@pytest.fixture
def folders(tmp_path):
    pdfs = tmp_path / "pdfs"
    packages = tmp_path / "packages"
    pdfs.mkdir()
    packages.mkdir()
    source = pdfs / "synthetic.pdf"
    with pdfium.PdfDocument.new() as doc:
        for _ in range(19):
            doc.new_page(100, 100).close()
        doc.save(source)
    package = json.loads((Path(__file__).resolve().parents[1] / "examples/demo/fukui_2027_codex.json").read_text())
    package["document"]["sha256"] = hashlib.sha256(source.read_bytes()).hexdigest()
    package["records"][0]["department"] = "=Synthetic spreadsheet formula"
    (packages / "example.json").write_text(json.dumps(package), encoding="utf-8")
    return pdfs, packages


def test_batch_exports_readable_data_without_confirmation(folders, tmp_path):
    batch = prepare_batch(*folders)
    output = tmp_path / "result"
    summary = write_bundle(batch, output)
    assert summary["records"] == 5
    assert summary["confirmed_records_written"] == 0
    records = [json.loads(line) for line in (output / "records.jsonl").read_text().splitlines()]
    assert records[0]["department"].startswith("=")
    assert "'=Synthetic" in (output / "records_table.csv").read_text(encoding="utf-8-sig")
    assert all(row["review_status"] == "needs_review" for row in records)
    assert "物理・化学・生物から2科目" in (output / "records_readable.md").read_text()
    queue = json.loads((output / "review_queue.json").read_text())
    assert all({"page", "quote", "current_value", "review_action", "review_question"} <= row.keys() for row in queue)
    assert records[0]["field_evidence"]["english_requirement"]["page"] == 10
    with pytest.raises(FileExistsError):
        write_bundle(batch, output)


def test_missing_extraction_stops_batch(folders):
    pdfs, packages = folders
    (packages / "example.json").unlink()
    with pytest.raises(ValueError, match="Codex reading still needed"):
        prepare_batch(pdfs, packages)


def test_duplicate_pdf_is_deduplicated_but_duplicate_packages_are_rejected(folders):
    pdfs, packages = folders
    (pdfs / "copy.PDF").write_bytes((pdfs / "synthetic.pdf").read_bytes())
    assert len(prepare_batch(pdfs, packages)) == 1
    (packages / "copy.json").write_bytes((packages / "example.json").read_bytes())
    with pytest.raises(ValueError, match="Multiple extraction packages"):
        prepare_batch(pdfs, packages)
