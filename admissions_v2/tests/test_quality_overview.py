from __future__ import annotations

import unittest
from unittest.mock import patch


class QualityOverviewTest(unittest.TestCase):
    def test_reports_per_seed_thin_critical_coverage_without_owner_todo(self) -> None:
        from scripts.quality_overview import build_quality_overview, format_owner_summary

        full_coverage = {
            "application_period": {"checked": 5, "passed": 5},
            "deadline_rule": {"checked": 5, "passed": 5},
            "enrollment_period": {"checked": 5, "passed": 5},
            "required_documents": {"checked": 5, "passed": 5},
            "eligibility": {"checked": 5, "passed": 5},
            "evidence": {"checked": 5, "passed": 5},
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
        thin_coverage = {
            **full_coverage,
            "deadline_rule": {"checked": 1, "passed": 1},
            "eju_session": {"checked": 1, "passed": 1},
        }

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 2, "passed": 2, "failed": 0, "skipped": 0},
                    "items": [
                        {"id": "wide-seed", "baseline": {"expected_count": 5, "field_coverage": full_coverage}},
                        {"id": "thin-seed", "baseline": {"expected_count": 5, "field_coverage": thin_coverage}},
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

        self.assertEqual(overview["overall_status"], "quality_gate_ready")
        self.assertEqual(overview["owner_todo"], [])
        self.assertEqual(
            overview["per_seed_thin_coverage"][0],
            {"seed": "thin-seed", "field": "deadline_rule", "checked": 1, "minimum": 3},
        )
        self.assertIn("thin seed coverage: thin-seed deadline_rule checked=1", format_owner_summary(overview))

    def test_does_not_report_single_record_seed_as_thin_coverage(self) -> None:
        from scripts.quality_overview import build_quality_overview

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "single-record-seed",
                            "baseline": {
                                "expected_count": 1,
                                "field_coverage": {
                                    "application_period": {"checked": 1, "passed": 1},
                                    "deadline_rule": {"checked": 1, "passed": 1},
                                },
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

        self.assertEqual(overview["per_seed_thin_coverage"], [])

    def test_reports_language_requirement_coverage_without_owner_todo(self) -> None:
        from scripts.quality_overview import build_quality_overview, format_owner_summary

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "language-seed",
                            "baseline": {
                                "field_coverage": {
                                    "application_period": {"checked": 5, "passed": 5},
                                    "deadline_rule": {"checked": 5, "passed": 5},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 8, "passed": 8},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "jlpt_requirement": {"checked": 2, "passed": 2},
                                    "english_requirement": {"checked": 6, "passed": 6},
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

        self.assertEqual(overview["language_requirement_coverage"]["jlpt_requirement"]["checked"], 2)
        self.assertEqual(overview["overall_status"], "quality_gate_ready")
        self.assertEqual(overview["owner_todo"], [])
        self.assertIn("language requirements: EJU Japanese checked=8; JLPT checked=2; English checked=6", format_owner_summary(overview))

    def test_can_include_non_blocking_source_text_health(self) -> None:
        from scripts.quality_overview import build_quality_overview, format_owner_summary

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
                                "expected_count": 12,
                                "field_coverage": {
                                    "application_period": {"checked": 5},
                                    "deadline_rule": {"checked": 5},
                                    "enrollment_period": {"checked": 5},
                                    "required_documents": {"checked": 5},
                                    "eligibility": {"checked": 5},
                                    "evidence": {"checked": 5},
                                    "eju_session": {"checked": 5},
                                    "eju_japanese": {"checked": 5},
                                    "eju_general": {"checked": 5},
                                    "eju_math": {"checked": 2},
                                    "eju_physics": {"checked": 1},
                                    "eju_chemistry": {"checked": 1},
                                    "english_requirement": {"checked": 5},
                                    "result_date": {"checked": 5},
                                    "screening_schedule": {"checked": 5},
                                },
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
            patch(
                "scripts.quality_overview.audit_seed_source_text_layers",
                return_value={
                    "passed": True,
                    "summary": {
                        "total": 1,
                        "readable": 0,
                        "manual_text_check_needed": 1,
                        "missing_source": 0,
                    },
                    "items": [
                        {
                            "id": "osaka_metropolitan_2027_undergrad",
                            "text_health": {"status": "garbled_text_layer", "requires_manual_text_check": True},
                        }
                    ],
                },
            ),
        ):
            overview = build_quality_overview(include_source_text_health=True)

        self.assertEqual(overview["overall_status"], "quality_gate_ready")
        self.assertEqual(overview["source_text_health"]["summary"]["manual_text_check_needed"], 1)
        self.assertIn("source text checks: 1 need manual/vision review", format_owner_summary(overview))

    def test_summary_includes_source_watchlist_and_review_queue(self) -> None:
        from scripts.quality_overview import build_quality_overview, format_owner_summary

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [{"id": "seed", "baseline": {"field_coverage": {}}}],
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
            patch(
                "scripts.quality_overview.build_source_watchlist",
                return_value=[
                    {
                        "stem": "sample",
                        "source_url": "https://example.test/sample.pdf",
                        "source_type": "pdf",
                        "last_known_sha256": "a" * 64,
                        "last_checked_at": "2026-05-26T00:00:00+00:00",
                        "source_note": "Official source.",
                    }
                ],
            ),
            patch(
                "scripts.quality_overview.load_review_queue",
                return_value={"summary": {"needs_review": 2}, "items": [{"stem": "sample"}]},
            ),
        ):
            overview = build_quality_overview()

        self.assertEqual(overview["source_watchlist"]["summary"]["total"], 1)
        self.assertEqual(overview["source_review_queue"]["summary"]["needs_review"], 2)
        summary = format_owner_summary(overview)
        self.assertIn("watched sources: 1", summary)
        self.assertIn("source review queue: 2 need review", summary)

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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 6, "passed": 6},
                                    "result_date": {"checked": 5, "passed": 5},
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

        weak_todos = [todo for todo in overview["quality_todo"] if todo["action"] == "expand_field_baseline"]
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertTrue(any(todo["field"] == "screening_schedule" for todo in weak_todos))

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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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

    def test_treats_required_documents_as_critical_field_coverage(self) -> None:
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
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "required_documents": {"checked": 4, "passed": 4},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
        self.assertEqual(critical[0]["field"], "required_documents")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_eligibility_as_critical_field_coverage(self) -> None:
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
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 4, "passed": 4},
                                    "evidence": {"checked": 5, "passed": 5},
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
        self.assertEqual(critical[0]["field"], "eligibility")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_evidence_as_critical_field_coverage(self) -> None:
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
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 4, "passed": 4},
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
        self.assertEqual(critical[0]["field"], "evidence")
        self.assertEqual(critical[0]["checked"], 4)
        self.assertEqual(critical[0]["minimum"], 5)

    def test_treats_seed_record_count_as_quality_gate(self) -> None:
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
                                "expected_count": 9,
                                "field_coverage": {
                                    "application_period": {"checked": 9, "passed": 9},
                                    "deadline_rule": {"checked": 9, "passed": 9},
                                    "enrollment_period": {"checked": 5, "passed": 5},
                                    "required_documents": {"checked": 9, "passed": 9},
                                    "eligibility": {"checked": 9, "passed": 9},
                                    "evidence": {"checked": 9, "passed": 9},
                                    "eju_session": {"checked": 5, "passed": 5},
                                    "eju_japanese": {"checked": 5, "passed": 5},
                                    "eju_general": {"checked": 5, "passed": 5},
                                    "eju_math": {"checked": 2, "passed": 2},
                                    "eju_physics": {"checked": 1, "passed": 1},
                                    "eju_chemistry": {"checked": 1, "passed": 1},
                                    "english_requirement": {"checked": 9, "passed": 9},
                                    "result_date": {"checked": 9, "passed": 9},
                                    "screening_schedule": {"checked": 9, "passed": 9},
                                },
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

        record_todos = [todo for todo in overview["quality_todo"] if todo["action"] == "seed_record_count_below_target"]
        self.assertEqual(overview["overall_status"], "needs_owner_action")
        self.assertEqual(record_todos[0]["seed"], "waseda-2027-official")
        self.assertEqual(record_todos[0]["checked"], 9)
        self.assertEqual(record_todos[0]["minimum"], 12)

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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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
                                    "required_documents": {"checked": 5, "passed": 5},
                                    "eligibility": {"checked": 5, "passed": 5},
                                    "evidence": {"checked": 5, "passed": 5},
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

    def test_does_not_create_owner_todo_for_sparse_noncritical_field(self) -> None:
        from scripts.quality_overview import build_quality_overview

        full_critical_coverage = {
            "application_period": {"checked": 5, "passed": 5},
            "deadline_rule": {"checked": 5, "passed": 5},
            "enrollment_period": {"checked": 5, "passed": 5},
            "required_documents": {"checked": 5, "passed": 5},
            "eligibility": {"checked": 5, "passed": 5},
            "evidence": {"checked": 5, "passed": 5},
            "eju_session": {"checked": 5, "passed": 5},
            "eju_japanese": {"checked": 5, "passed": 5},
            "eju_general": {"checked": 5, "passed": 5},
            "eju_math": {"checked": 2, "passed": 2},
            "eju_physics": {"checked": 1, "passed": 1},
            "eju_chemistry": {"checked": 1, "passed": 1},
            "english_requirement": {"checked": 5, "passed": 5},
            "result_date": {"checked": 5, "passed": 5},
            "screening_schedule": {"checked": 5, "passed": 5},
            "jlpt_requirement": {"checked": 2, "passed": 2},
        }

        with (
            patch(
                "scripts.quality_overview.run_seed_baseline_suite",
                return_value={
                    "passed": True,
                    "summary": {"total": 1, "passed": 1, "failed": 0, "skipped": 0},
                    "items": [
                        {
                            "id": "chukyo-gakuin-2027-undergrad",
                            "baseline": {"expected_count": 2, "field_coverage": full_critical_coverage},
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
        self.assertNotIn("jlpt_requirement", weak_fields)

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
