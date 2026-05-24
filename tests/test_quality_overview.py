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
                    "summary": {"baseline_files": 2, "missing_local_sources": 1, "missing_seed_extractors": 1},
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


if __name__ == "__main__":
    unittest.main()
