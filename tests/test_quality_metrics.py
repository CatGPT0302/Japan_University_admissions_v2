from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path


class QualityMetricsTest(unittest.TestCase):
    def _load_db(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "quality_metrics_test.db")
        for name in ("DATABASE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
            os.environ.pop(name, None)
        sys.modules.pop("scripts.db", None)
        db = importlib.import_module("scripts.db")
        db.init_db()
        return db

    def test_quality_metrics_reflect_manual_corrections(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            db = self._load_db(Path(tmp))
            doc_id = db.create_source_document("Quality University", "quality.pdf", "/tmp/quality.pdf", "", "2027")
            staging_id = db.insert_staging_record(
                doc_id,
                3,
                {
                    "university": "Quality University",
                    "admission_year": "2027",
                    "faculty": "Law",
                    "department": "Law",
                    "application_period": "",
                    "eju_session": "2025-11",
                    "english_requirement": "",
                    "screening_method": "Document review",
                    "confidence": 0.42,
                    "risk_level": "high",
                    "needs_review": True,
                },
            )

            db.update_staging_record(
                staging_id,
                {
                    "application_period": "2026-06-01 to 2026-06-08",
                    "english_requirement": "TOEFL iBT",
                    "is_reviewed": 1,
                },
            )
            metrics = db.get_quality_metrics(doc_id)
            corrections = db.get_correction_events(doc_id)

        modified_by_field = {item["field"]: item["modified"] for item in metrics["field_coverage"]}
        fill_by_field = {item["field"]: item["filled"] for item in metrics["field_coverage"]}

        self.assertEqual(metrics["total_staging_records"], 1)
        self.assertEqual(fill_by_field["application_period"], 1)
        self.assertEqual(fill_by_field["english_requirement"], 1)
        self.assertEqual(modified_by_field["application_period"], 1)
        self.assertEqual(modified_by_field["english_requirement"], 1)
        self.assertEqual(
            {item["field"] for item in metrics["top_modified_fields"][:2]},
            {"english_requirement", "application_period"},
        )
        self.assertEqual(len(corrections), 2)
        self.assertEqual({item["field_name"] for item in corrections}, {"application_period", "english_requirement"})


if __name__ == "__main__":
    unittest.main()
