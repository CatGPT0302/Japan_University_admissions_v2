"""
Regression test for Waseda 2027.

Usage:
    python regression_waseda_2027.py              # report only (uses latest doc)
    python regression_waseda_2027.py --run-pipeline  # run pipeline first
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "database" / "admissions_v2.db"

WASEDA_FACULTIES = {
    "政治経済学部", "法学部", "教育学部", "商学部", "社会科学部",
    "文化構想学部", "文学部",
    "基幹理工学部", "創造理工学部", "先進理工学部",
    "人間科学部", "スポーツ科学部",
}

EXPECTED_RECORD_COUNT_MIN = 12   # at least one record per faculty


def _latest_doc_id(conn: sqlite3.Connection, file_name: str) -> int:
    row = conn.execute(
        "SELECT max(id) AS id FROM source_documents WHERE file_name=?", (file_name,)
    ).fetchone()
    return int(row["id"]) if row and row["id"] else 0


def report(doc_id: int) -> None:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row

    rows = [dict(r) for r in conn.execute(
        "SELECT * FROM admission_records_staging WHERE document_id=?", (doc_id,)
    ).fetchall()]

    print(f"\n{'='*60}")
    print(f"DOC_ID: {doc_id}")
    print(f"TOTAL_RECORDS: {len(rows)}")

    # Faculty coverage
    found_faculties = {r["faculty"] for r in rows if r.get("faculty")}
    missing = WASEDA_FACULTIES - found_faculties
    extra = found_faculties - WASEDA_FACULTIES
    print(f"\nFACULTY_COVERAGE: {len(found_faculties)}/{len(WASEDA_FACULTIES)}")
    if missing:
        print(f"  MISSING_FACULTIES: {sorted(missing)}")
    if extra:
        print(f"  UNEXPECTED_FACULTIES: {sorted(extra)}")

    # needs_review
    nr = sum(1 for r in rows if r.get("needs_review"))
    print(f"\nNEEDS_REVIEW_COUNT: {nr} / {len(rows)}")

    # English empty
    eng_empty = [r for r in rows if not str(r.get("english_requirement") or "").strip()
                 or str(r.get("english_requirement") or "").strip() in {"-", "－", "ー"}]
    print(f"\nENGLISH_EMPTY_COUNT: {len(eng_empty)}")
    for r in eng_empty[:10]:
        print(f"  {r['faculty']} / {r['department']}")

    # Date presence
    no_dates = [r for r in rows
                if not str(r.get("screening_schedule") or "").strip()
                and not str(r.get("result_date") or "").strip()]
    print(f"\nNO_DATES_COUNT: {len(no_dates)}")
    for r in no_dates[:10]:
        print(f"  {r['faculty']} / {r['department']}")

    # Warnings summary
    all_warnings = []
    for r in rows:
        w = r.get("warnings_json") or "[]"
        try:
            all_warnings.extend(json.loads(w))
        except Exception:
            pass
    from collections import Counter
    top_warnings = Counter(all_warnings).most_common(10)
    print(f"\nTOP_WARNINGS:")
    for msg, cnt in top_warnings:
        print(f"  [{cnt}] {msg}")

    print(f"\n{'='*60}")
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", default="input_pdfs/01_2027_gaikokugakusei_nyushiyoukou.pdf")
    parser.add_argument("--run-pipeline", action="store_true")
    parser.add_argument("--pages", nargs="*", type=int, help="Specific pages to process")
    args = parser.parse_args()

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
        return

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    doc_id = _latest_doc_id(conn, Path(args.pdf).name)
    conn.close()

    if not doc_id:
        print("No document found in DB. Run with --run-pipeline first.")
        return

    report(doc_id)


if __name__ == "__main__":
    main()
