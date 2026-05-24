from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import extract_direct
from scripts import db
from scripts.quality_baseline import evaluate_against_expected, load_json_records

INPUT_DIR = ROOT / "input_pdfs"

GOLDEN_SAMPLES = [
    {"university": "明治大学", "year": "2026", "file_name": "meiji_2026.pdf"},
    {"university": "早稲田大学", "year": "2026", "file_name": "早稻田_2026.pdf"},
    {"university": "中央大学", "year": "2026", "file_name": "中央_2026.pdf"},
    {"university": "立教大学", "year": "2026", "file_name": "立教_2026.pdf"},
]

KEY_FIELDS = [
    "application_period",
    "deadline_rule",
    "eju_session",
    "eju_japanese",
    "eju_general",
    "eju_math",
    "english_requirement",
    "screening_method",
    "screening_schedule",
    "result_date",
    "enrollment_period",
]


def _latest_doc_id(file_name: str) -> int | None:
    conn = sqlite3.connect(str(db.SQLITE_PATH))
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT MAX(id) AS id FROM source_documents WHERE file_name=?", (file_name,)).fetchone()
    conn.close()
    doc_id = int((dict(row) if row else {}).get("id") or 0)
    return doc_id or None


def _sample_report(sample: dict[str, str], doc_id: int) -> dict[str, Any]:
    rows = db.get_staging_records(doc_id)
    total = len(rows)
    field_coverage: dict[str, int] = {}
    for field in KEY_FIELDS:
        field_coverage[field] = sum(1 for row in rows if str(row.get(field) or "").strip())
    risk = {"high": 0, "medium": 0, "low": 0}
    for row in rows:
        key = str(row.get("risk_level") or "medium")
        if key not in risk:
            risk[key] = 0
        risk[key] += 1
    return {
        "university": sample["university"],
        "year": sample["year"],
        "file_name": sample["file_name"],
        "doc_id": doc_id,
        "staging_records": total,
        "risk_distribution": risk,
        "field_coverage_count": field_coverage,
        "field_coverage_rate": {
            field: round((count / total) if total else 0.0, 4)
            for field, count in field_coverage.items()
        },
    }


def _baseline_path(baseline_dir: Path, file_name: str) -> Path:
    return baseline_dir / f"{Path(file_name).stem}.expected.json"


def _attach_baseline_report(
    item: dict[str, Any],
    sample: dict[str, str],
    doc_id: int,
    baseline_dir: Path,
    min_exact_match_rate: float,
) -> dict[str, Any]:
    expected_path = _baseline_path(baseline_dir, sample["file_name"])
    if not expected_path.exists():
        item["baseline"] = {
            "status": "missing_expected",
            "expected_path": str(expected_path),
        }
        return item

    expected_records = load_json_records(expected_path)
    extracted_records = db.get_staging_records(doc_id)
    report = evaluate_against_expected(
        expected_records,
        extracted_records,
        min_exact_match_rate=min_exact_match_rate,
    )
    item["baseline"] = {
        "status": "passed" if report["passed"] else "failed",
        "expected_path": str(expected_path),
        "summary": report["summary"],
        "records": report["records"],
    }
    return item


def main() -> int:
    parser = argparse.ArgumentParser(description="Run golden sample regression checks for admissions_v2.")
    parser.add_argument("--run-extract", action="store_true", help="Run extraction before reading metrics.")
    parser.add_argument("--save-json", default="", help="Optional path to save JSON report.")
    parser.add_argument("--baseline-dir", default="", help="Directory containing <pdf-stem>.expected.json files.")
    parser.add_argument("--min-exact-match-rate", type=float, default=0.95)
    args = parser.parse_args()

    db.init_db()

    report_rows: list[dict[str, Any]] = []
    for sample in GOLDEN_SAMPLES:
        pdf_path = INPUT_DIR / sample["file_name"]
        if not pdf_path.exists():
            report_rows.append(
                {
                    "university": sample["university"],
                    "year": sample["year"],
                    "file_name": sample["file_name"],
                    "status": "missing_pdf",
                }
            )
            continue

        if args.run_extract:
            extraction = extract_direct.run_extraction(
                pdf_path=pdf_path,
                university=sample["university"],
                year=sample["year"],
                url="",
            )
            doc_id = int(extraction.get("doc_id") or 0)
        else:
            doc_id = int(_latest_doc_id(sample["file_name"]) or 0)

        if not doc_id:
            report_rows.append(
                {
                    "university": sample["university"],
                    "year": sample["year"],
                    "file_name": sample["file_name"],
                    "status": "missing_doc",
                }
            )
            continue

        item = _sample_report(sample, doc_id)
        if args.baseline_dir:
            item = _attach_baseline_report(
                item,
                sample,
                doc_id,
                Path(args.baseline_dir),
                float(args.min_exact_match_rate),
            )
        item["status"] = "ok"
        report_rows.append(item)

    baseline_reports = [row.get("baseline") for row in report_rows if isinstance(row.get("baseline"), dict)]
    baseline_passed = all(row.get("status") == "passed" for row in baseline_reports) if baseline_reports else None
    output = {
        "run_extract": bool(args.run_extract),
        "sample_count": len(GOLDEN_SAMPLES),
        "baseline_passed": baseline_passed,
        "reports": report_rows,
    }
    payload = json.dumps(output, ensure_ascii=False, indent=2)
    print(payload)

    save_path = args.save_json.strip()
    if save_path:
        Path(save_path).write_text(payload, encoding="utf-8")

    return 1 if baseline_passed is False else 0


if __name__ == "__main__":
    raise SystemExit(main())
