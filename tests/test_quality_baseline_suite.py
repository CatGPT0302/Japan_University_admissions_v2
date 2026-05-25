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
        self.assertIn({"id": "draft-law", "failure": "missing_source_note"}, failures)
        self.assertIn({"id": "draft-law", "failure": "baseline_not_human_checked"}, failures)
        self.assertIn({"id": "missing-expect", "failure": "missing_source_note"}, failures)
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
                            "source_note": "Checked against official PDF page 1.",
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

    def test_default_suite_reports_registered_seed_without_local_source_as_skipped(self) -> None:
        from scripts.quality_baseline_suite import run_seed_baseline_suite

        report = run_seed_baseline_suite()

        skipped = [item for item in report["items"] if item["status"] == "skipped"]
        self.assertGreaterEqual(report["summary"]["skipped"], 1)
        self.assertTrue(any(item["id"] == "waseda-2027-official" for item in skipped))
        self.assertIn("missing_source", skipped[0]["failures"])

    def test_suite_can_enforce_minimum_field_coverage(self) -> None:
        from scripts.quality_baseline_suite import run_seed_baseline_suite

        with TemporaryDirectory() as tmp:
            expected_path = Path(tmp) / "expected.json"
            expected_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "seed-law",
                            "source_document": "https://example.test/source.pdf",
                            "source_note": "Checked against official PDF page 1.",
                            "match": {"faculty": "Law"},
                            "expect": {"screening_schedule": {"contains": ["December"]}},
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
                        "records": [{"faculty": "Law", "screening_schedule": "December 5"}],
                    }
                ],
                min_field_coverage={"screening_schedule": 2},
            )

        self.assertFalse(report["passed"])
        self.assertEqual(report["items"][0]["status"], "failed")
        self.assertIn("field_coverage_below_minimum", report["items"][0]["failures"])
        self.assertEqual(report["items"][0]["field_coverage_failures"][0]["field"], "screening_schedule")


if __name__ == "__main__":
    unittest.main()
