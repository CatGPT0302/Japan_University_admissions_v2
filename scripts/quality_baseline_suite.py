from __future__ import annotations

import argparse
import json
import sys
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
from scripts.seed_registry import registered_seed_extractors  # noqa: E402


def validate_baseline_records(records: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    for index, record in enumerate(records, start=1):
        record_id = str(record.get("id") or f"expected-{index}")
        if not str(record.get("source_document") or "").strip():
            failures.append({"id": record_id, "failure": "missing_source_document"})
        if not str(record.get("source_note") or "").strip():
            failures.append({"id": record_id, "failure": "missing_source_note"})
        if not isinstance(record.get("match"), dict) or not record.get("match"):
            failures.append({"id": record_id, "failure": "missing_match"})
        if not isinstance(record.get("expect"), dict) or not record.get("expect"):
            failures.append({"id": record_id, "failure": "missing_expect"})
        if record.get("review_status") != "human_checked_seed":
            failures.append({"id": record_id, "failure": "baseline_not_human_checked"})
    return failures


def _read_pdf_text(path: Path) -> str:
    pages = extract_text_per_page(path)
    return "\n".join(text for _page, text in sorted(pages.items()))


def _default_seed_items() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for seed in registered_seed_extractors().values():
        candidates = list(seed.get("source_candidates") or [])
        source_path = ROOT / candidates[0] if candidates else Path("")
        items.append(
            {
                "id": seed.get("id"),
                "expected_path": ROOT / str(seed.get("expected_path") or ""),
                "source_path": source_path,
                "extractor": seed.get("extractor"),
            }
        )
    return items


def _records_for_item(item: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    if isinstance(item.get("records"), list):
        return [record for record in item["records"] if isinstance(record, dict)], None

    source_path = Path(item.get("source_path") or "")
    if not source_path.exists():
        return [], "missing_source"

    extractor = item.get("extractor")
    if not callable(extractor):
        return [], "missing_extractor"

    return [record for record in extractor(_read_pdf_text(source_path)) if isinstance(record, dict)], None


def run_seed_baseline_suite(
    items: list[dict[str, Any]] | None = None,
    *,
    min_exact_match_rate: float = 0.95,
    min_field_coverage: dict[str, int] | None = None,
) -> dict[str, Any]:
    suite_items = items if items is not None else _default_seed_items()
    reports: list[dict[str, Any]] = []
    field_targets = min_field_coverage or {}

    for item in suite_items:
        item_id = str(item.get("id") or f"seed-{len(reports) + 1}")
        expected_path = Path(item.get("expected_path") or "")
        failures: list[str] = []

        if not expected_path.exists():
            reports.append(
                {
                    "id": item_id,
                    "status": "failed",
                    "expected_path": str(expected_path),
                    "failures": ["missing_expected"],
                }
            )
            continue

        expected_records = load_json_records(expected_path)
        metadata_failures = validate_baseline_records(expected_records)
        if metadata_failures:
            failures.append("baseline_metadata_invalid")

        extracted_records, record_error = _records_for_item(item)
        if record_error:
            failures.append(record_error)

        if record_error == "missing_source":
            reports.append(
                {
                    "id": item_id,
                    "status": "skipped",
                    "expected_path": str(expected_path),
                    "source_path": str(item.get("source_path") or ""),
                    "extracted_count": 0,
                    "failures": failures,
                    "metadata_failures": metadata_failures,
                    "baseline": None,
                }
            )
            continue

        baseline_report = evaluate_against_expected(
            expected_records,
            extracted_records,
            min_exact_match_rate=min_exact_match_rate,
        )
        if not baseline_report["passed"]:
            failures.append("baseline_mismatch")
        field_coverage_failures = []
        coverage = baseline_report.get("field_coverage") if isinstance(baseline_report, dict) else {}
        for field, minimum in field_targets.items():
            stats = coverage.get(field) if isinstance(coverage, dict) else {}
            checked = int(stats.get("checked") or 0) if isinstance(stats, dict) else 0
            if checked < int(minimum):
                field_coverage_failures.append({"field": field, "checked": checked, "minimum": int(minimum)})
        if field_coverage_failures:
            failures.append("field_coverage_below_minimum")

        reports.append(
            {
                "id": item_id,
                "status": "passed" if not failures else "failed",
                "expected_path": str(expected_path),
                "extracted_count": len(extracted_records),
                "failures": failures,
                "metadata_failures": metadata_failures,
                "field_coverage_failures": field_coverage_failures,
                "baseline": baseline_report,
            }
        )

    passed_count = sum(1 for item in reports if item["status"] == "passed")
    failed_count = sum(1 for item in reports if item["status"] == "failed")
    skipped_count = sum(1 for item in reports if item["status"] == "skipped")
    return {
        "passed": failed_count == 0,
        "summary": {
            "total": len(reports),
            "passed": passed_count,
            "failed": failed_count,
            "skipped": skipped_count,
        },
        "items": reports,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run human-checked seed baseline checks for deterministic extractors.")
    parser.add_argument("--output", default="", help="Optional path to write the JSON report.")
    parser.add_argument("--min-exact-match-rate", type=float, default=0.95)
    parser.add_argument(
        "--min-field-coverage",
        action="append",
        default=[],
        help="Optional field coverage gate in the form field=count. Repeat as needed.",
    )
    args = parser.parse_args(argv)

    min_field_coverage: dict[str, int] = {}
    for value in args.min_field_coverage:
        field, _, raw_count = str(value).partition("=")
        if field.strip() and raw_count.strip():
            min_field_coverage[field.strip()] = int(raw_count.strip())

    report = run_seed_baseline_suite(
        min_exact_match_rate=args.min_exact_match_rate,
        min_field_coverage=min_field_coverage,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
