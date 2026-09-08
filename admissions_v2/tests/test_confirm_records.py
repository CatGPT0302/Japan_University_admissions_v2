from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path


def _load_db(db_path: Path):
    os.environ["SQLITE_PATH"] = str(db_path)
    for name in (
        "DATABASE_URL",
        "DATABASE_PUBLIC_URL",
        "POSTGRES_URL",
        "POSTGRES_PRISMA_URL",
        "POSTGRES_URL_NON_POOLING",
    ):
        os.environ.pop(name, None)
    sys.modules.pop("scripts.db", None)
    db = importlib.import_module("scripts.db")
    db.init_db()
    return db


def test_confirm_keeps_distinct_admission_routes_for_same_department(tmp_path: Path) -> None:
    db = _load_db(tmp_path / "confirm.db")
    doc_id = db.create_source_document(
        "明治大学",
        "meiji.pdf",
        str(tmp_path / "meiji.pdf"),
        "https://example.test/meiji.pdf",
        "2027",
    )
    shared = {
        "university": "明治大学",
        "admission_year": "2027",
        "faculty": "商学部",
        "department": "商学科",
        "application_period": "2026年8月25日～9月1日",
        "is_reviewed": 1,
        "needs_review": 0,
    }
    db.insert_staging_record(
        doc_id,
        1,
        {
            **shared,
            "screening_method": "书面审查",
            "screening_schedule": "",
            "result_date": "2026年12月11日",
        },
    )
    db.insert_staging_record(
        doc_id,
        2,
        {
            **shared,
            "screening_method": "书面审查 / 面试",
            "screening_schedule": "2026年12月5日",
            "result_date": "2026年12月11日",
        },
    )

    result = db.confirm_all_by_doc(doc_id)
    repeated = db.confirm_all_by_doc(doc_id)
    conn = db.get_conn()
    records = conn.execute(
        "SELECT screening_method FROM admission_records ORDER BY id"
    ).fetchall()
    conn.close()

    assert result["processed"] == 2
    assert result["written"] == 2
    assert repeated["written"] == 0
    assert {row["screening_method"] for row in records} == {
        "书面审查",
        "书面审查 / 面试",
    }
