from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class QualityGapReportTest(unittest.TestCase):
    def test_reports_seed_coverage_missing_sources_and_next_actions(self) -> None:
        from scripts.quality_gap_report import build_quality_gap_report

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "quality_baselines"
            upload_dir = root / "data" / "uploads"
            baseline_dir.mkdir(parents=True)
            upload_dir.mkdir(parents=True)

            (baseline_dir / "meiji_2027_schedule.expected.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "meiji-law",
                            "source_document": "https://example.test/meiji.pdf",
                            "match": {"university": "Meiji", "faculty": "Law"},
                            "expect": {"english_requirement": "TOEFL"},
                            "review_status": "human_checked_seed",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (baseline_dir / "waseda_2027_official.expected.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "waseda-law",
                            "source_document": "https://example.test/waseda.pdf",
                            "match": {"university": "Waseda", "faculty": "Law"},
                            "expect": {"english_requirement": "TOEFL"},
                            "review_status": "human_checked_seed",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (upload_dir / "meiji_2027_schedule_official.pdf").write_bytes(
                "%PDF-1.4 fake 明治大学 2027".encode("utf-8")
            )

            report = build_quality_gap_report(root=root)

        self.assertEqual(report["summary"]["baseline_files"], 2)
        self.assertEqual(report["summary"]["human_checked_records"], 2)
        self.assertEqual(report["summary"]["registered_seed_extractors"], 1)
        self.assertEqual(report["summary"]["missing_local_sources"], 1)
        self.assertEqual(report["summary"]["missing_seed_extractors"], 1)
        waseda = next(item for item in report["baseline_files"] if item["stem"].startswith("waseda"))
        self.assertEqual(waseda["status"], "needs_source_and_extractor")
        self.assertIn("add_local_source_pdf", waseda["next_actions"])
        self.assertIn("add_seed_extractor_or_pipeline_fixture", waseda["next_actions"])
        self.assertEqual(report["owner_todo"][0]["baseline"], "waseda_2027_official")
        self.assertEqual(report["owner_todo"][0]["action"], "add_local_source_pdf")
        self.assertIn("data/uploads/waseda_2027_official.pdf", report["owner_todo"][0]["details"])
        self.assertEqual(report["owner_todo"][1]["action"], "add_seed_extractor_or_pipeline_fixture")

    def test_waseda_moves_to_extractor_todo_once_source_pdf_exists(self) -> None:
        from scripts.quality_gap_report import build_quality_gap_report

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "quality_baselines"
            upload_dir = root / "data" / "uploads"
            baseline_dir.mkdir(parents=True)
            upload_dir.mkdir(parents=True)
            (baseline_dir / "waseda_2027_official.expected.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "waseda-law",
                            "source_document": "https://example.test/waseda.pdf",
                            "match": {"university": "Waseda", "faculty": "Law"},
                            "expect": {"english_requirement": "TOEFL"},
                            "review_status": "human_checked_seed",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (upload_dir / "waseda_2027_official.pdf").write_bytes(
                "%PDF-1.4 checked source Waseda 2027 早稲田大学".encode("utf-8")
            )

            report = build_quality_gap_report(root=root)

        waseda = report["baseline_files"][0]
        self.assertTrue(waseda["local_source_available"])
        self.assertEqual(waseda["source_candidates"][0], "data/uploads/waseda_2027_official.pdf")
        self.assertEqual(waseda["status"], "needs_seed_extractor")
        self.assertEqual(report["summary"]["missing_local_sources"], 0)
        self.assertEqual(report["owner_todo"][0]["action"], "add_seed_extractor_or_pipeline_fixture")

    def test_wrong_pdf_marker_does_not_count_as_available_source(self) -> None:
        from scripts.quality_gap_report import build_quality_gap_report

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_dir = root / "quality_baselines"
            upload_dir = root / "data" / "uploads"
            baseline_dir.mkdir(parents=True)
            upload_dir.mkdir(parents=True)
            (baseline_dir / "waseda_2027_official.expected.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "waseda-law",
                            "source_document": "https://example.test/waseda.pdf",
                            "match": {"university": "Waseda", "faculty": "Law"},
                            "expect": {"english_requirement": "TOEFL"},
                            "review_status": "human_checked_seed",
                        }
                    ]
                ),
                encoding="utf-8",
            )
            (upload_dir / "waseda_2027_official.pdf").write_bytes(b"%PDF-1.4 unrelated university 2026")

            report = build_quality_gap_report(root=root)

        waseda = report["baseline_files"][0]
        self.assertFalse(waseda["local_source_available"])
        self.assertEqual(waseda["source_validation"]["status"], "marker_mismatch")
        self.assertEqual(waseda["status"], "needs_source_and_extractor")

    def test_pdf_text_layer_is_used_for_source_marker_validation(self) -> None:
        from scripts.quality_gap_report import _validate_local_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            upload_dir = root / "data" / "uploads"
            upload_dir.mkdir(parents=True)
            (upload_dir / "meiji.pdf").write_bytes(b"%PDF-1.4 binary text without plain markers")

            with patch(
                "scripts.quality_gap_report.extract_text_per_page",
                return_value={1: "明治大学 2027年度外国人留学生入学試験"},
            ):
                validation = _validate_local_source(
                    root,
                    ["data/uploads/meiji.pdf"],
                    ["明治大学", "2027"],
                )

        self.assertTrue(validation["available"])
        self.assertEqual(validation["status"], "matched")


if __name__ == "__main__":
    unittest.main()
