from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


class QualityBaselineTest(unittest.TestCase):
    def test_evaluates_exact_matches_missing_values_and_unexpected_values(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected

        expected = [
            {
                "id": "waseda-law",
                "match": {"university": "Waseda", "faculty": "Law", "department": "Law"},
                "expect": {
                    "application_period": "2026-06-01 to 2026-06-08",
                    "eju_session": "2025-11 or 2026-06",
                    "english_requirement": "TOEFL iBT",
                },
            },
            {
                "id": "waseda-commerce",
                "match": {"university": "Waseda", "faculty": "Commerce", "department": "Commerce"},
                "expect": {
                    "application_period": "2026-06-01 to 2026-06-08",
                    "screening_method": "Document review and interview",
                },
            },
        ]
        extracted = [
            {
                "university": "Waseda",
                "faculty": "Law",
                "department": "Law",
                "application_period": "2026-06-01 to 2026-06-08",
                "eju_session": "2025-11 or 2026-06",
                "english_requirement": "",
            },
            {
                "university": "Waseda",
                "faculty": "Commerce",
                "department": "Commerce",
                "application_period": "2026-06-01 to 2026-06-08",
                "screening_method": "Document review only",
            },
        ]

        report = evaluate_against_expected(expected, extracted)

        self.assertFalse(report["passed"])
        self.assertEqual(report["expected_count"], 2)
        self.assertEqual(report["matched_record_count"], 2)
        self.assertEqual(report["summary"]["checked_items"], 5)
        self.assertEqual(report["summary"]["passed_items"], 3)
        self.assertEqual(report["summary"]["missing_items"], 1)
        self.assertEqual(report["summary"]["mismatched_items"], 1)
        self.assertEqual(report["summary"]["exact_match_rate"], 0.6)
        self.assertEqual(report["records"][0]["status"], "failed")
        self.assertEqual(report["records"][0]["checks"][2]["status"], "missing")
        self.assertEqual(report["records"][1]["checks"][1]["status"], "mismatch")

    def test_supports_contains_expectations_for_long_text(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected

        expected = [
            {
                "id": "long-note",
                "match": {"faculty": "Science"},
                "expect": {
                    "eju_science": {"contains": ["Physics", "Chemistry"]},
                    "english_requirement": {"any_of": ["TOEFL", "IELTS"]},
                    "result_date": {"optional": True},
                },
            }
        ]
        extracted = [
            {
                "faculty": "Science",
                "eju_science": "Applicants choose Physics and Chemistry.",
                "english_requirement": "IELTS Academic",
                "result_date": "",
            }
        ]

        report = evaluate_against_expected(expected, extracted, min_exact_match_rate=1.0)

        self.assertTrue(report["passed"])
        self.assertEqual(report["summary"]["checked_items"], 2)
        self.assertEqual(report["summary"]["optional_empty_items"], 1)
        self.assertEqual(report["summary"]["exact_match_rate"], 1.0)

    def test_marks_unmatched_expected_records_as_failed(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected

        report = evaluate_against_expected(
            [{"id": "missing", "match": {"faculty": "Policy"}, "expect": {"application_period": "June"}}],
            [{"faculty": "Law", "application_period": "June"}],
        )

        self.assertFalse(report["passed"])
        self.assertEqual(report["matched_record_count"], 0)
        self.assertEqual(report["summary"]["unmatched_records"], 1)
        self.assertEqual(report["records"][0]["status"], "unmatched")

    def test_cli_writes_report_and_returns_failure_when_baseline_fails(self) -> None:
        import json

        from scripts.quality_baseline import main

        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            expected_path = tmp_path / "expected.json"
            extracted_path = tmp_path / "extracted.json"
            report_path = tmp_path / "report.json"
            expected_path.write_text(
                json.dumps(
                    [
                        {
                            "id": "law",
                            "match": {"faculty": "Law"},
                            "expect": {"application_period": "June"},
                        }
                    ]
                ),
                encoding="utf-8",
            )
            extracted_path.write_text(json.dumps([{"faculty": "Law", "application_period": ""}]), encoding="utf-8")

            exit_code = main(
                [
                    "--expected",
                    str(expected_path),
                    "--extracted",
                    str(extracted_path),
                    "--output",
                    str(report_path),
                ]
            )

            self.assertEqual(exit_code, 1)
            report = json.loads(report_path.read_text(encoding="utf-8"))
            self.assertFalse(report["passed"])
            self.assertEqual(report["summary"]["missing_items"], 1)

    def test_waseda_seed_baseline_is_loadable_and_marked_checked(self) -> None:
        from scripts.quality_baseline import load_json_records

        records = load_json_records(ROOT / "quality_baselines" / "waseda_2027_official.expected.json")

        self.assertGreaterEqual(len(records), 5)
        self.assertTrue(all(record.get("review_status") == "human_checked_seed" for record in records))
        self.assertTrue(all(record.get("match", {}).get("university") == "早稲田大学" for record in records))
        self.assertTrue(all("application_period" in record.get("expect", {}) for record in records))


if __name__ == "__main__":
    unittest.main()
