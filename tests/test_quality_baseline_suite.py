from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class QualityBaselineSuiteTest(unittest.TestCase):
    def test_suite_reports_registered_seed_passes(self) -> None:
        from scripts.quality_baseline_suite import run_seed_baseline_suite

        with TemporaryDirectory() as tmp:
            expected_path = Path(tmp) / "expected.json"
            expected_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "seed-law",
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
        self.assertIn("baseline_not_human_checked", report["items"][0]["failures"])


if __name__ == "__main__":
    unittest.main()
