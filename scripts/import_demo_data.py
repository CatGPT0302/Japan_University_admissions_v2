"""Validate Codex-authored PDF records and import them into demo staging only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys

from scripts.local_demo import DEFAULT_DEMO_ROOT, demo_environment

TEXT_FIELDS = {
    "university", "admission_year", "admission_period", "faculty", "department",
    "application_period", "deadline_rule", "eju_session", "eju_japanese",
    "eju_general", "eju_math", "eju_physics", "eju_chemistry", "eju_biology",
    "english_requirement", "screening_method", "screening_schedule", "result_date",
    "enrollment_period", "prefecture", "campus", "required_documents", "eligibility", "evidence",
}
REQUIRED = {
    "university", "admission_year", "faculty", "department", "application_period",
    "deadline_rule", "eju_session", "eju_japanese", "eju_general", "eju_math",
    "eju_physics", "eju_chemistry", "eju_biology", "english_requirement",
}


def validate_package(package: dict, source: Path) -> list[dict]:
    """Check structure and provenance; this does not certify factual accuracy."""
    if not isinstance(package, dict) or set(package) != {"document", "records"}:
        raise ValueError("Expected document and records only")
    document = package["document"]
    if not isinstance(document, dict) or set(document) != {"university", "year", "source_url", "sha256"}:
        raise ValueError("Invalid document metadata")
    if not all(isinstance(v, str) and v.strip() for v in document.values()):
        raise ValueError("Document metadata must be nonempty text")
    if not document["source_url"].startswith("https://"):
        raise ValueError("A public HTTPS source URL is required")
    if len(document["year"]) != 4 or not document["year"].isdigit():
        raise ValueError("Expected four-digit admission year")
    content = source.read_bytes()
    if not content.startswith(b"%PDF-"):
        raise ValueError("Source is not a PDF")
    if hashlib.sha256(content).hexdigest() != document["sha256"]:
        raise ValueError("Source PDF sha256 mismatch")
    import pypdfium2 as pdfium

    with pdfium.PdfDocument(source) as pdf:
        page_count = len(pdf)
    records = package["records"]
    if not isinstance(records, list) or not records:
        raise ValueError("At least one record is required")
    result = []
    identities = set()
    for index, record in enumerate(records, 1):
        if not isinstance(record, dict) or set(record) - (TEXT_FIELDS | {"field_evidence", "warnings"}):
            raise ValueError(f"Record {index}: unsupported fields")
        for key in REQUIRED:
            if not isinstance(record.get(key), str) or not record[key].strip():
                raise ValueError(f"Record {index}: missing {key}; explicitly state if not documented")
        if any(not isinstance(record[key], str) for key in TEXT_FIELDS & record.keys()):
            raise ValueError(f"Record {index}: data values must be text")
        if record["university"] != document["university"] or record["admission_year"] != document["year"]:
            raise ValueError(f"Record {index}: document identity mismatch")
        identity = tuple(record.get(key, "") for key in ("faculty", "department", "admission_period"))
        if identity in identities:
            raise ValueError(f"Record {index}: duplicate program")
        identities.add(identity)
        evidence = record.get("field_evidence")
        if not isinstance(evidence, dict) or set(evidence) - TEXT_FIELDS:
            raise ValueError(f"Record {index}: invalid evidence fields")
        for key in (REQUIRED | set(evidence)):
            item = evidence.get(key)
            if (not isinstance(item, dict) or set(item) != {"page", "text"}
                    or type(item["page"]) is not int or not 1 <= item["page"] <= page_count
                    or not isinstance(item["text"], str) or not item["text"].strip()):
                raise ValueError(f"Record {index}: missing or invalid physical-page evidence for {key}")
        warnings = record.get("warnings", [])
        if not isinstance(warnings, list) or any(not isinstance(w, str) or not w.strip() for w in warnings):
            raise ValueError(f"Record {index}: invalid warnings")
        row = {key: value for key, value in record.items() if key in TEXT_FIELDS}
        row.update(field_evidence=evidence, warnings_json=warnings,
                   needs_review=1, is_reviewed=0, risk_level="high", confidence=0,
                   field_confidence={}, manual_modified_fields=[], reviewed_at="",
                   raw_llm_json="")
        result.append(row)
    return result


def import_package(package: dict, source: Path, *, apply: bool = False) -> dict:
    rows = validate_package(package, source)
    summary = {"status": "validated", "records": len(rows), "next_step": "human_review",
               "confirmed_records_written": 0}
    if not apply:
        return summary
    # DB configuration is captured at import time; never reuse a preloaded DB module.
    if "scripts.db" in sys.modules:
        raise RuntimeError("Run this importer in a fresh process to guarantee demo isolation")
    env = demo_environment(DEFAULT_DEMO_ROOT, dict(os.environ))
    os.environ.clear()
    os.environ.update(env)
    from scripts import db

    db.init_db()
    fingerprint = hashlib.sha256(json.dumps(package, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    filename = f"codex-{fingerprint}.pdf"
    existing = [d for d in db.get_documents(query=filename) if d["filename"] == filename]
    if existing:
        if len(existing) != 1 or existing[0]["staging_count"] != len(rows):
            raise RuntimeError("Incomplete prior import found; inspect the demo document before retrying")
        return {**summary, "status": "already_imported", "doc_id": existing[0]["doc_id"]}
    target = Path(env["UPLOAD_DIR"]) / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).hexdigest() != package["document"]["sha256"]:
            raise ValueError("Existing demo PDF has different contents")
    else:
        shutil.copyfile(source, target)
    document = package["document"]
    doc_id = db.create_source_document(document["university"], filename, str(target),
                                       document["source_url"], document["year"])
    try:
        for row in rows:
            db.insert_staging_record(doc_id, row["field_evidence"]["faculty"]["page"], row)
        db.update_source_document(doc_id, status="extracted")
    except Exception:
        db.delete_document(doc_id)
        raise
    return {**summary, "status": "imported", "doc_id": doc_id}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--apply", action="store_true", help="Write to the isolated demo database")
    args = parser.parse_args()
    try:
        package = json.loads(args.package.read_text(encoding="utf-8"))
        print(json.dumps(import_package(package, args.source_pdf, apply=args.apply), ensure_ascii=False))
    except (ValueError, OSError, RuntimeError) as exc:
        parser.exit(1, f"Import failed: {exc}\n")


if __name__ == "__main__":
    main()
