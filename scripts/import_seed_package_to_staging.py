from __future__ import annotations

import argparse
import importlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(path)
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        payload = json.loads(line)
        if isinstance(payload, dict):
            rows.append(payload)
    return rows


def _package_documents(package_dir: Path) -> dict[str, dict[str, Any]]:
    documents_path = package_dir / "documents.json"
    if not documents_path.exists():
        return {}
    documents = _read_json(documents_path)
    if not isinstance(documents, list):
        return {}
    return {str(item.get("seed_id") or item.get("stem") or ""): item for item in documents if isinstance(item, dict)}


def _group_records(records: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        key = str(record.get("seed_id") or record.get("source_document") or "seed-package")
        grouped[key].append(record)
    return dict(grouped)


def _staging_record(record: dict[str, Any]) -> dict[str, Any]:
    warnings = record.get("warnings")
    if not isinstance(warnings, list):
        warnings = [str(warnings)] if str(warnings or "").strip() else []
    warnings = [*warnings, "Imported from a human-checked seed package; review before confirming."]
    shaped = dict(record)
    shaped["needs_review"] = 1
    shaped["is_reviewed"] = 0
    shaped["warnings"] = warnings
    shaped["warnings_json"] = warnings
    shaped["raw_llm_json"] = {
        "source": "seed_data_package",
        "seed_id": record.get("seed_id", ""),
        "seed_record_id": record.get("seed_record_id", ""),
        "database_status": record.get("database_status", "not_imported"),
    }
    return shaped


def _existing_seed_document(db: Any, *, file_name: str, university: str, admission_year: str) -> dict[str, Any] | None:
    rows = db.get_documents(query=file_name, year=admission_year or None, limit=50, offset=0)
    for row in rows:
        if (
            str(row.get("filename") or "") == file_name
            and str(row.get("university_name") or "") == university
            and str(row.get("admission_year") or "") == admission_year
        ):
            return row
    return None


def import_seed_package_to_staging(*, package_dir: Path, apply: bool = False) -> dict[str, Any]:
    records = _read_jsonl(package_dir / "records.jsonl")
    documents = _package_documents(package_dir)
    grouped = _group_records(records)
    summary = {
        "mode": "apply" if apply else "dry_run",
        "package_dir": str(package_dir),
        "documents": len(grouped),
        "records": len(records),
        "created_documents": 0,
        "created_staging_records": 0,
        "skipped_existing_documents": 0,
        "database_status": "staging_imported" if apply else "not_imported",
    }
    details: list[dict[str, Any]] = []

    if not apply:
        for seed_id, seed_records in sorted(grouped.items()):
            doc = documents.get(seed_id, {})
            details.append(
                {
                    "seed_id": seed_id,
                    "university": doc.get("university") or seed_records[0].get("university", ""),
                    "admission_year": doc.get("admission_year") or seed_records[0].get("admission_year", ""),
                    "records": len(seed_records),
                    "status": "would_import_to_staging",
                }
            )
        return {"summary": summary, "items": details}

    db = importlib.import_module("scripts.db")
    db.init_db()
    for seed_id, seed_records in sorted(grouped.items()):
        doc = documents.get(seed_id, {})
        first = seed_records[0]
        university = str(doc.get("university") or first.get("university") or "")
        admission_year = str(doc.get("admission_year") or first.get("admission_year") or "")
        source_document = str(doc.get("source_document") or first.get("source_document") or f"{seed_id}.pdf")
        source_url = str(doc.get("source_url") or first.get("source_url") or first.get("pdf_url") or "")
        file_name = f"seed-package-{source_document}"
        existing = _existing_seed_document(db, file_name=file_name, university=university, admission_year=admission_year)
        if existing and (int(existing.get("staging_count") or 0) > 0 or int(existing.get("confirmed_count") or 0) > 0):
            summary["skipped_existing_documents"] += 1
            details.append(
                {
                    "seed_id": seed_id,
                    "doc_id": existing.get("doc_id"),
                    "university": university,
                    "admission_year": admission_year,
                    "records": len(seed_records),
                    "status": "skipped_existing",
                }
            )
            continue
        doc_id = db.create_source_document(
            university,
            file_name,
            str(package_dir / "records.jsonl"),
            source_url,
            admission_year,
        )
        created_rows = 0
        for record in seed_records:
            db.insert_staging_record(doc_id, None, _staging_record(record))
            created_rows += 1
        summary["created_documents"] += 1
        summary["created_staging_records"] += created_rows
        details.append(
            {
                "seed_id": seed_id,
                "doc_id": doc_id,
                "university": university,
                "admission_year": admission_year,
                "records": created_rows,
                "status": "imported_to_staging",
            }
        )
    return {"summary": summary, "items": details}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a seed data package into staging for owner review. Dry-run by default.")
    parser.add_argument("--package-dir", default="data/exports/seed_data_package")
    parser.add_argument("--apply", action="store_true", help="Actually create source documents and staging rows. Without this flag, only prints a dry-run summary.")
    args = parser.parse_args(argv)
    payload = import_seed_package_to_staging(package_dir=Path(args.package_dir), apply=args.apply)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
