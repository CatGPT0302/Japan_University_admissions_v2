from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.quality_baseline import evaluate_against_expected, load_json_records  # noqa: E402
from scripts.quality_baseline_suite import validate_baseline_records  # noqa: E402
from scripts.seed_registry import registered_seed_extractors  # noqa: E402


TABLE_COLUMNS = [
    "seed_id",
    "university",
    "admission_year",
    "faculty",
    "department",
    "application_period",
    "screening_method",
    "screening_schedule",
    "result_date",
    "eju_japanese",
    "english_requirement",
    "required_documents",
    "source_url",
]


def _read_pdf_text(path: Path) -> str:
    pages = extract_text_per_page(path)
    return "\n".join(text for _page, text in sorted(pages.items()))


def _default_items(root: Path = ROOT) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for seed in registered_seed_extractors().values():
        candidates = list(seed.get("source_candidates") or [])
        source_path = root / candidates[0] if candidates else Path("")
        items.append(
            {
                "seed_id": seed.get("id") or seed.get("stem"),
                "stem": seed.get("stem"),
                "university": seed.get("university"),
                "admission_year": seed.get("admission_year"),
                "source_url": seed.get("source_url"),
                "source_path": source_path,
                "expected_path": root / str(seed.get("expected_path") or ""),
                "extractor": seed.get("extractor"),
            }
        )
    return items


def _records_for_item(item: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    if isinstance(item.get("records"), list):
        return [record for record in item["records"] if isinstance(record, dict)], ""
    if item.get("source_text"):
        extractor = item.get("extractor")
        if not callable(extractor):
            return [], "missing_extractor"
        return [record for record in extractor(str(item.get("source_text") or "")) if isinstance(record, dict)], ""

    source_path = Path(item.get("source_path") or "")
    if not source_path.exists():
        return [], "missing_source"
    extractor = item.get("extractor")
    if not callable(extractor):
        return [], "missing_extractor"
    return [record for record in extractor(_read_pdf_text(source_path)) if isinstance(record, dict)], ""


def _expected_for_item(item: dict[str, Any]) -> tuple[list[dict[str, Any]], str]:
    if isinstance(item.get("expected_records"), list):
        return [record for record in item["expected_records"] if isinstance(record, dict)], ""
    expected_path = Path(item.get("expected_path") or "")
    if not expected_path.exists():
        return [], "missing_expected"
    return load_json_records(expected_path), ""


def _source_document_name(item: dict[str, Any]) -> str:
    source_path = Path(item.get("source_path") or "")
    if source_path.name:
        return source_path.name
    return str(item.get("stem") or item.get("seed_id") or "")


def _shape_record(record: dict[str, Any], item: dict[str, Any], index: int) -> dict[str, Any]:
    seed_id = str(item.get("seed_id") or item.get("stem") or "")
    shaped = dict(record)
    shaped.setdefault("university", item.get("university") or "")
    shaped.setdefault("admission_year", item.get("admission_year") or "")
    shaped.setdefault("source_url", item.get("source_url") or record.get("pdf_url") or "")
    shaped.setdefault("pdf_url", item.get("source_url") or record.get("pdf_url") or "")
    shaped["seed_id"] = seed_id
    shaped["seed_record_id"] = str(record.get("id") or f"{seed_id}-{index}")
    shaped["source_document"] = _source_document_name(item)
    shaped["review_status"] = "human_checked_seed_package"
    shaped["database_status"] = "not_imported"
    return shaped


def _review_items(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for record in records:
        warnings = record.get("warnings")
        needs_review = bool(record.get("needs_review") or warnings)
        if not needs_review:
            continue
        items.append(
            {
                "seed_id": record.get("seed_id", ""),
                "seed_record_id": record.get("seed_record_id", ""),
                "university": record.get("university", ""),
                "admission_year": record.get("admission_year", ""),
                "faculty": record.get("faculty", ""),
                "department": record.get("department", ""),
                "source_document": record.get("source_document", ""),
                "source_url": record.get("source_url", ""),
                "reason": "seed record asks for review" if record.get("needs_review") else "seed record has warnings",
                "warnings": warnings or [],
            }
        )
    return items


def build_seed_data_package(
    *,
    output_dir: Path,
    items: list[dict[str, Any]] | None = None,
    include_failed: bool = False,
    now: str | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    seed_items = items if items is not None else _default_items()
    generated_at = now or datetime.now(timezone.utc).replace(microsecond=0).isoformat()

    documents: list[dict[str, Any]] = []
    records: list[dict[str, Any]] = []

    for item in seed_items:
        seed_id = str(item.get("seed_id") or item.get("stem") or f"seed-{len(documents) + 1}")
        expected_records, expected_error = _expected_for_item(item)
        extracted_records, record_error = _records_for_item(item)
        metadata_failures = validate_baseline_records(expected_records) if expected_records else []
        baseline = None
        status = "passed"
        failures = [failure for failure in [expected_error, record_error] if failure]
        if not expected_records:
            failures.append("missing_expected_records")
        if metadata_failures:
            failures.append("baseline_metadata_invalid")
        if expected_records and extracted_records:
            baseline = evaluate_against_expected(expected_records, extracted_records)
            if not baseline.get("passed"):
                failures.append("baseline_mismatch")
        if failures:
            status = "failed"

        documents.append(
            {
                "seed_id": seed_id,
                "stem": item.get("stem") or "",
                "university": item.get("university") or "",
                "admission_year": item.get("admission_year") or "",
                "source_document": _source_document_name(item),
                "source_path": str(item.get("source_path") or ""),
                "source_url": item.get("source_url") or "",
                "expected_path": str(item.get("expected_path") or ""),
                "record_count": len(extracted_records),
                "status": status,
                "failures": failures,
                "baseline_summary": baseline.get("summary", {}) if isinstance(baseline, dict) else {},
            }
        )
        if status == "passed" or include_failed:
            records.extend(_shape_record(record, item, index) for index, record in enumerate(extracted_records, start=1))

    review_items = _review_items(records)
    summary = {
        "generated_at": generated_at,
        "documents": len(documents),
        "passed_documents": sum(1 for item in documents if item["status"] == "passed"),
        "failed_documents": sum(1 for item in documents if item["status"] == "failed"),
        "records": len(records),
        "review_items": len(review_items),
        "database_status": "not_imported",
    }

    (output_dir / "package_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "documents.json").write_text(json.dumps(documents, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_dir / "review_queue.json").write_text(
        json.dumps({"summary": {"items": len(review_items)}, "items": review_items}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "records.jsonl").open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    with (output_dir / "records_table.csv").open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TABLE_COLUMNS)
        writer.writeheader()
        for record in records:
            writer.writerow({column: record.get(column, "") for column in TABLE_COLUMNS})
    return {"summary": summary, "documents": documents, "records": records, "review_items": review_items}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build a reviewable data package from human-checked seed extractors without mutating the database.")
    parser.add_argument("--output-dir", default="data/exports/seed_data_package", help="Directory for package_summary.json, documents.json, records.jsonl, records_table.csv, and review_queue.json.")
    parser.add_argument("--include-failed", action="store_true", help="Include records from failed seed checks. Off by default.")
    args = parser.parse_args(argv)

    payload = build_seed_data_package(output_dir=Path(args.output_dir), include_failed=args.include_failed)
    print(json.dumps(payload["summary"], ensure_ascii=False, indent=2))
    return 0 if payload["summary"]["failed_documents"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
