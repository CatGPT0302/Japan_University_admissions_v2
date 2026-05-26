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
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 6, "passed": 6},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
                                    "optional_notes": {"checked": 1, "passed": 1},
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
        self.assertEqual(overview["next_owner_action"]["field"], "optional_notes")
        self.assertEqual(overview["quality_todo"][0]["checked"], 1)

    def test_adds_owner_todo_when_critical_field_coverage_is_below_target(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 2, "passed": 2, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 2, "passed": 2},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 6, "passed": 6},
                                    "result_date": {"checked": 6, "passed": 6},
                                    "screening_schedule": {"checked": 6, "passed": 6},
                                }
                            },
                        },
                        {
                            "id": "waseda-2027-official",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 2, "passed": 2},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
                                }
                            },
                        },
                    ],
                },
            ),
            patch(
                "scripts.quality_overview.build_quality_gap_report",
                return_value={
                    "summary": {
                        "baseline_files": 2,
                        "registered_seed_extractors": 2,
                        "missing_local_sources": 0,
                        "missing_seed_extractors": 0,
                    },
                    "owner_todo": [],
                },
            ),
        ):
            overview = build_quality_overview()

        self.assertEqual(overview["overall_status"], "needs_owner_action")
        critical = [todo for todo in overview["quality_todo"] if todo["action"] == "critical_field_coverage_below_target"]
        self.assertEqual(critical[0]["field"], "application_period")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_eju_session_as_critical_field_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 4, "passed": 4},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
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

        critical = [todo for todo in overview["quality_todo"] if todo["action"] == "critical_field_coverage_below_target"]
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(critical[0]["field"], "eju_session")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_deadline_rule_as_critical_field_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "waseda-2027-official",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 4, "passed": 4},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
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

        critical = [todo for todo in overview["quality_todo"] if todo["action"] == "critical_field_coverage_below_target"]
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(critical[0]["field"], "deadline_rule")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_enrollment_period_as_critical_field_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "waseda-2027-official",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 4, "passed": 4},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
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

        critical = [todo for todo in overview["quality_todo"] if todo["action"] == "critical_field_coverage_below_target"]
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(critical[0]["field"], "enrollment_period")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_granular_eju_subjects_as_critical_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 4, "passed": 4},
                                    "eju_general": {"checked": 4, "passed": 4},
                                    "eju_math": {"checked": 1, "passed": 1},
                                    "eju_physics": {"checked": 0, "passed": 0},
                                    "eju_chemistry": {"checked": 0, "passed": 0},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
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

        critical = [todo for todo in overview["quality_todo"] if todo["action"] == "critical_field_coverage_below_target"]
        by_field = {todo["field"]: todo for todo in critical}
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(by_field["eju_japanese"]["minimum"], 5)
        self.assertEqual(by_field["eju_general"]["minimum"], 5)
        self.assertEqual(by_field["eju_math"]["minimum"], 2)
        self.assertEqual(by_field["eju_physics"]["minimum"], 1)
        self.assertEqual(by_field["eju_chemistry"]["minimum"], 1)

    def test_does_not_mark_critical_field_as_weak_when_it_meets_target(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "meiji-2027-schedule",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 5, "passed": 5},
                                    "result_date": {"checked": 5, "passed": 5},
                                    "screening_schedule": {"checked": 5, "passed": 5},
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

        weak_fields = [todo["field"] for todo in overview["quality_todo"] if todo["action"] == "expand_field_baseline"]
        self.assertEqual(overview["overall_status"], "quality_gate_ready")
        self.assertNotIn("eju_math", weak_fields)

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
