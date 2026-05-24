from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class QualityBaselineSuiteTest(unittest.TestCase):
    def test_validates_baseline_records_require_source_match_expect_and_review_status(self) -> None:
        from scripts.quality_baseline_suite import validate_baseline_records

        failures = validate_baseline_records(
            [
                {
                    "id": "draft-law",
                    "match": {"faculty": "Law"},
                    "expect": {"english_requirement": "TOEFL"},
                    "review_status": "draft_needs_human_check",
                },
                {
                    "id": "missing-expect",
                    "source_document": "https://example.test/source.pdf",
                    "match": {"faculty": "Commerce"},
                    "review_status": "human_checked_seed",
                },
            ]
        )

        self.assertIn({"id": "draft-law", "failure": "missing_source_document"}, failures)
        self.assertIn({"id": "draft-law", "failure": "baseline_not_human_checked"}, failures)
        self.assertIn({"id": "missing-expect", "failure": "missing_expect"}, failures)

    def test_suite_reports_registered_seed_passes(self) -> None:
        from scripts.quality_baseline_suite import run_seed_baseline_suite

        with TemporaryDirectory() as tmp:
            expected_path = Path(tmp) / "expected.json"
            expected_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "seed-law",
                            "source_document": "https://example.test/source.pdf",
                            "match": {"university": "Meiji", "faculty": "Law"},
                            "expect": {"english_requirement": {"contains": ["TOEFL"]}},
                            "review_status": "human_checked_seed",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            report = run_seed_baseline_suite(
                [
                    {
                        "id": "sample-seed",
                        "expected_path": expected_path,
                        "records": [{"university": "Meiji", "faculty": "Law", "english_requirement": "TOEFL iBT"}],
                    }
                ]
            )

        self.assertTrue(report["passed"], report)
        self.assertEqual(report["summary"]["passed"], 1)
        self.assertEqual(report["summary"]["failed"], 0)
        self.assertEqual(report["items"][0]["status"], "passed")

    def test_suite_fails_when_human_checked_seed_metadata_is_missing(self) -> None:
        from scripts.quality_baseline_suite import run_seed_baseline_suite

        with TemporaryDirectory() as tmp:
            expected_path = Path(tmp) / "expected.json"
            expected_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "seed-law",
                            "match": {"university": "Meiji", "faculty": "Law"},
                            "expect": {"english_requirement": "TOEFL iBT"},
                        }
                    ]
                ),
                encoding="utf-8",
            )

            report = run_seed_baseline_suite(
                [
                    {
                        "id": "sample-seed",
                        "expected_path": expected_path,
                        "records": [{"university": "Meiji", "faculty": "Law", "english_requirement": "TOEFL iBT"}],
                    }
                ]
            )

        self.assertFalse(report["passed"])
        self.assertEqual(report["items"][0]["status"], "failed")
        self.assertIn("baseline_metadata_invalid", report["items"][0]["failures"])
        self.assertIn(
            {"id": "seed-law", "failure": "baseline_not_human_checked"},
            report["items"][0]["metadata_failures"],
        )


if __name__ == "__main__":
    unittest.main()
