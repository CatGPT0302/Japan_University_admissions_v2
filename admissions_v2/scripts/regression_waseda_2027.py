"""
Regression gate for Waseda 2027 extraction quality.

Usage:
    python scripts/regression_waseda_2027.py
    python scripts/regression_waseda_2027.py --enforce
    python scripts/regression_waseda_2027.py --run-pipeline --enforce
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import db  # noqa: E402

DB_PATH = db.SQLITE_PATH

WASEDA_FACULTIES = {
    "政治経済学部",
    "法学部",
    "教育学部",
    "商学部",
    "社会科学部",
    "文化構想学部",
    "文学部",
    "基幹理工学部",
    "創造理工学部",
    "先進理工学部",
    "人間科学部",
    "スポーツ科学部",
}

EXPECTED_RECORD_COUNT_MIN = 12
MAX_ENGLISH_EMPTY = 0
MAX_NO_DATES = 0


def _latest_doc_id(conn: sqlite3.Connection, file_name: str) -> int:
    row = conn.execute(
        "SELECT max(id) AS id FROM source_documents WHERE file_name=?",
        (file_name,),
    ).fetchone()
    return int(row["id"]) if row and row["id"] else 0


def _is_empty_english(value: Any) -> bool:
    text = str(value or "").strip()
    return not text or text in {"-", "ー", "なし", "不要", "該当なし"}


def evaluate_waseda_rows(
    rows: list[dict[str, Any]],
    *,
    expected_faculties: set[str] | None = None,
    min_record_count: int = EXPECTED_RECORD_COUNT_MIN,
    max_english_empty: int = MAX_ENGLISH_EMPTY,
    max_no_dates: int = MAX_NO_DATES,
) -> dict[str, Any]:
    expected = expected_faculties or WASEDA_FACULTIES
    found_faculties = {str(row.get("faculty") or "").strip() for row in rows if str(row.get("faculty") or "").strip()}
    missing = sorted(expected - found_faculties)
    unexpected = sorted(found_faculties - expected)
    needs_review_count = sum(1 for row in rows if row.get("needs_review"))
    english_empty = [row for row in rows if _is_empty_english(row.get("english_requirement"))]
    no_dates = [
        row
        for row in rows
        if not str(row.get("screening_schedule") or "").strip()
        and not str(row.get("result_date") or "").strip()
    ]
    warnings: list[str] = []
    for row in rows:
        raw = row.get("warnings_json") or row.get("warnings") or []
        if isinstance(raw, str):
            try:
                raw = json.loads(raw)
            except Exception:
                raw = [raw] if raw else []
        if isinstance(raw, list):
            warnings.extend(str(item) for item in raw if str(item).strip())

    failures: list[str] = []
    if len(rows) < min_record_count:
        failures.append("record_count_below_minimum")
    if missing:
        failures.append("missing_expected_faculties")
    if unexpected:
        failures.append("unexpected_faculties")
    if len(english_empty) > max_english_empty:
        failures.append("english_requirements_missing")
    if len(no_dates) > max_no_dates:
        failures.append("dates_missing")

    return {
        "passed": not failures,
        "failures": failures,
        "total_records": len(rows),
        "min_record_count": min_record_count,
        "faculty_coverage": {
            "found": sorted(found_faculties),
            "found_count": len(found_faculties),
            "expected_count": len(expected),
            "missing": missing,
            "unexpected": unexpected,
        },
        "needs_review_count": needs_review_count,
        "english_empty_count": len(english_empty),
        "english_empty_records": [
            {"faculty": row.get("faculty"), "department": row.get("department")} for row in english_empty[:10]
        ],
        "no_dates_count": len(no_dates),
        "no_dates_records": [
            {"faculty": row.get("faculty"), "department": row.get("department")} for row in no_dates[:10]
        ],
        "top_warnings": [
            {"message": message, "count": count}
            for message, count in Counter(warnings).most_common(10)
        ],
    }


def _load_rows(doc_id: int) -> list[dict[str, Any]]:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    rows = [
        dict(row)
        for row in conn.execute(
            "SELECT * FROM admission_records_staging WHERE document_id=?",
            (doc_id,),
        ).fetchall()
    ]
    conn.close()
    return rows


def report(doc_id: int) -> dict[str, Any]:
    output = {"doc_id": doc_id, **evaluate_waseda_rows(_load_rows(doc_id))}
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="input_pdfs/01_2027_gaikokugakusei_nyushiyoukou.pdf")
    parser.add_argument("--run-pipeline", action="store_true")
    parser.add_argument("--pages", nargs="*", type=int, help="Specific pages to process")
    parser.add_argument("--enforce", action="store_true", help="Exit non-zero when the Waseda quality gate fails.")
    parser.add_argument("--save-json", default="", help="Optional path to write the JSON report.")
    args = parser.parse_args(argv)

    if args.run_pipeline:
        from scripts.pipeline import run_pipeline

        summary = run_pipeline(
            pdf_path=Path(args.pdf),
            university="早稲田大学",
            admission_year="2027",
            pdf_url="https://www.waseda.jp/inst/admission/undergraduate/system/international/",
            pages=args.pages,
        )
        print("PIPELINE_SUMMARY:", summary)

    if not DB_PATH.exists():
        print("Database not found. Run with --run-pipeline first.")
        return 1 if args.enforce else 0

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    doc_id = _latest_doc_id(conn, Path(args.pdf).name)
    conn.close()

    if not doc_id:
        print("No document found in DB. Run with --run-pipeline first.")
        return 1 if args.enforce else 0

    output = report(doc_id)
    if args.save_json:
        Path(args.save_json).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    return 1 if args.enforce and not output["passed"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
