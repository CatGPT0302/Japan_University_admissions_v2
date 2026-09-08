import json

from scripts.audit_acceptance import audit


def test_excluded_source_is_not_pending_and_empty_input_is_not_passed(tmp_path):
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"universities": [
        {"name": "Excluded", "acceptance_status": "excluded_by_user", "pdfs": [{"id": "main"}]},
        {"name": "Pending", "pdfs": [{"id": "main"}]},
    ]}))
    pdfs, packages = tmp_path / "pdfs", tmp_path / "packages"
    pdfs.mkdir()
    packages.mkdir()
    result = audit(manifest, pdfs, packages)
    assert result["structural_status"] == "failed"
    assert result["coverage"][0]["status"] == "excluded_by_user"
    assert result["coverage"][0]["pending_pdf_ids"] == []
    assert result["coverage"][1]["pending_pdf_ids"] == ["main"]
    assert result["publication_ready"] is False


def test_invalid_package_does_not_count_as_covered(tmp_path):
    digest = "a" * 64
    manifest = tmp_path / "manifest.json"
    manifest.write_text(json.dumps({"universities": [{"name": "Example",
        "pdfs": [{"id": "main", "sha256": digest}]}]}))
    pdfs, packages = tmp_path / "pdfs", tmp_path / "packages"
    pdfs.mkdir()
    packages.mkdir()
    (packages / "invalid.json").write_text(json.dumps({"document": {"sha256": digest}}))
    result = audit(manifest, pdfs, packages)
    assert result["structural_status"] == "failed"
    assert result["documents"] == 0
    assert result["coverage"][0]["status"] == "pending"
