from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path


class SeedDataPackageTest(unittest.TestCase):
    def test_builds_reviewable_package_without_database_import(self) -> None:
        from scripts.seed_data_package import build_seed_data_package

        def extractor(_text: str):
            return [
                {
                    "university": "Sample University",
                    "admission_year": "2027",
                    "faculty": "Letters",
                    "department": "Japanese",
                    "application_period": "2026-09-01 - 2026-09-10",
                    "screening_method": "Documents",
                    "screening_schedule": "2026-11-01",
                    "result_date": "2026-12-01",
                    "eju_japanese": "Japanese required",
                    "english_requirement": "TOEFL",
                    "required_documents": "Transcript",
                    "needs_review": True,
                    "warnings": ["Check department name"],
                }
            ]

        expected_records = [
            {
                "id": "sample-letters",
                "source_document": "https://example.test/sample.pdf",
                "source_note": "Official checked sample.",
                "match": {"university": "Sample University", "admission_year": "2027", "faculty": "Letters"},
                "expect": {
                    "application_period": {"contains": ["2026-09-01"]},
                    "screening_method": {"contains": ["Documents"]},
                    "eju_japanese": {"contains": ["Japanese"]},
                },
                "review_status": "human_checked_seed",
            }
        ]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            output_dir = Path(tmp) / "package"
            payload = build_seed_data_package(
                output_dir=output_dir,
                items=[
                    {
                        "seed_id": "sample-seed",
                        "stem": "sample",
                        "university": "Sample University",
                        "admission_year": "2027",
                        "source_url": "https://example.test/sample.pdf",
                        "source_text": "sample text",
                        "extractor": extractor,
                        "expected_records": expected_records,
                    }
                ],
                now="2026-05-27T00:00:00+00:00",
            )

            summary = json.loads((output_dir / "package_summary.json").read_text(encoding="utf-8"))
            documents = json.loads((output_dir / "documents.json").read_text(encoding="utf-8"))
            review_queue = json.loads((output_dir / "review_queue.json").read_text(encoding="utf-8"))
            records = [
                json.loads(line)
                for line in (output_dir / "records.jsonl").read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            csv_text = (output_dir / "records_table.csv").read_text(encoding="utf-8-sig")

        self.assertEqual(payload["summary"]["failed_documents"], 0)
        self.assertEqual(summary["records"], 1)
        self.assertEqual(summary["database_status"], "not_imported")
        self.assertEqual(documents[0]["status"], "passed")
        self.assertIn("source_path", documents[0])
        self.assertEqual(records[0]["database_status"], "not_imported")
        self.assertEqual(records[0]["review_status"], "human_checked_seed_package")
        self.assertEqual(review_queue["summary"]["items"], 1)
        self.assertIn("Sample University", csv_text)

    def test_failed_seed_is_not_exported_by_default(self) -> None:
        from scripts.seed_data_package import build_seed_data_package

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            payload = build_seed_data_package(
                output_dir=Path(tmp) / "package",
                items=[
                    {
                        "seed_id": "broken-seed",
                        "records": [{"university": "Broken University"}],
                        "expected_records": [],
                    }
                ],
                now="2026-05-27T00:00:00+00:00",
            )

        self.assertEqual(payload["summary"]["failed_documents"], 1)
        self.assertEqual(payload["summary"]["records"], 0)


if __name__ == "__main__":
    unittest.main()
