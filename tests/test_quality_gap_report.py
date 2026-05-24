from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


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
            (upload_dir / "meiji_2027_schedule_official.pdf").write_bytes(b"%PDF-1.4 fake")

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


if __name__ == "__main__":
    unittest.main()
