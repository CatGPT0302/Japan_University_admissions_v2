from __future__ import annotations

import unittest
from unittest.mock import patch


class QualityOverviewTest(unittest.TestCase):
    def test_combines_seed_suite_gap_report_and_owner_next_action(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={"passed": True, "summary": {"total": 1, "passed": 1, "failed": 0}},
            ),
            patch(
                "scripts.quality_overview.build_quality_gap_report",
                return_value={
                    "summary": {
                        "baseline_files": 2,
                        "registered_seed_extractors": 2,
                        "missing_local_sources": 1,
                        "missing_seed_extractors": 0,
                    },
                    "owner_todo": [
                        {
                            "priority": 10,
                            "baseline": "waseda_2027_official",
                            "action": "add_local_source_pdf",
                            "details": "Place the checked source PDF at data/uploads/waseda_2027_official.pdf.",
                        }
                    ],
                },
            ),
        ):
            overview = build_quality_overview()

        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertTrue(overview["seed_suite"]["passed"])
        self.assertEqual(overview["gap_report"]["summary"]["missing_local_sources"], 1)
        self.assertEqual(overview["next_owner_action"]["baseline"], "waseda_2027_official")
        self.assertEqual(overview["next_owner_action"]["action"], "add_local_source_pdf")

    def test_adds_owner_todo_for_weak_field_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 2, "passed": 1, "failed": 0, "skipped": 1},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "expected_path": "quality_baselines/meiji_2027_schedule.expected.json",
                            "baseline": {
                                "field_coverage": {
                                    "english_requirement": {"checked": 6, "passed": 6},
                                    "screening_schedule": {"checked": 1, "passed": 1},
                                }
                            },
                        }
                    ],
                },
            ),
            patch(
                "scripts.quality_overview.build_quality_gap_report",
                return_value={
                    "summary": {
                        "baseline_files": 1,
                        "registered_seed_extractors": 1,
                        "missing_local_sources": 0,
                        "missing_seed_extractors": 0,
                    },
                    "owner_todo": [],
                },
            ),
        ):
            overview = build_quality_overview()

        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(overview["next_owner_action"]["action"], "expand_field_baseline")
        self.assertEqual(overview["next_owner_action"]["field"], "screening_schedule")
        self.assertEqual(overview["quality_todo"][0]["checked"], 1)

    def test_formats_compact_summary_for_owner(self) -> None:
        from scripts.quality_overview import format_owner_summary

        summary = format_owner_summary(
            {
                "overall_status": "needs_owner_action",
                "seed_suite": {
                    "passed": True,
                    "summary": {"total": 2, "passed": 1, "failed": 0, "skipped": 1},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "baseline": {
                                "field_coverage": {
                                    "english_requirement": {"checked": 6, "passed": 6, "missing": 0, "mismatched": 0},
                                    "screening_schedule": {"checked": 1, "passed": 1, "missing": 0, "mismatched": 0},
                                }
                            },
                        }
                    ],
                },
                "gap_report": {
                    "summary": {
                        "baseline_files": 2,
                        "missing_local_sources": 1,
                        "registered_seed_extractors": 2,
                        "missing_seed_extractors": 0,
                    }
                },
                "next_owner_action": {
                    "baseline": "waseda_2027_official",
                    "action": "add_local_source_pdf",
                    "details": "Place the checked source PDF at data/uploads/waseda_2027_official.pdf.",
                },
            }
        )

        self.assertIn("status: needs_owner_action", summary)
        self.assertIn("seed suite: 1/2 passed, 1 skipped", summary)
        self.assertIn("registered extractors: 2", summary)
        self.assertIn("weak field coverage: screening_schedule checked=1", summary)
        self.assertIn("missing local sources: 1", summary)
        self.assertIn("missing seed extractors: 0", summary)
        self.assertIn("next: waseda_2027_official -> add_local_source_pdf", summary)
        self.assertIn("data/uploads/waseda_2027_official.pdf", summary)


if __name__ == "__main__":
    unittest.main()
