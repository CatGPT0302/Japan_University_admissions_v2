from __future__ import annotations

import unittest


class WasedaRegressionGateTest(unittest.TestCase):
    def test_passes_when_expected_faculties_and_required_content_are_present(self) -> None:
        from scripts.regression_waseda_2027 import evaluate_waseda_rows

        report = evaluate_waseda_rows(
            [
                {
                    "faculty": "Law",
                    "department": "Law",
                    "english_requirement": "TOEFL iBT",
                    "screening_schedule": "2026-09-01",
                    "result_date": "",
                    "needs_review": 1,
                },
                {
                    "faculty": "Commerce",
                    "department": "Commerce",
                    "english_requirement": "IELTS",
                    "screening_schedule": "",
                    "result_date": "2026-10-01",
                    "needs_review": 1,
                },
            ],
            expected_faculties={"Law", "Commerce"},
            min_record_count=2,
        )

        self.assertTrue(report["passed"])
        self.assertEqual(report["faculty_coverage"]["missing"], [])
        self.assertEqual(report["english_empty_count"], 0)
        self.assertEqual(report["no_dates_count"], 0)

    def test_fails_when_faculties_or_required_content_are_missing(self) -> None:
        from scripts.regression_waseda_2027 import evaluate_waseda_rows

        report = evaluate_waseda_rows(
            [
                {
                    "faculty": "Law",
                    "department": "Law",
                    "english_requirement": "",
                    "screening_schedule": "",
                    "result_date": "",
                    "needs_review": 0,
                }
            ],
            expected_faculties={"Law", "Commerce"},
            min_record_count=2,
        )

        self.assertFalse(report["passed"])
        self.assertIn("record_count_below_minimum", report["failures"])
        self.assertIn("missing_expected_faculties", report["failures"])
        self.assertIn("english_requirements_missing", report["failures"])
        self.assertIn("dates_missing", report["failures"])


if __name__ == "__main__":
    unittest.main()
