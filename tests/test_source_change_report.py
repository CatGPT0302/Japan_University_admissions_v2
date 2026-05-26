from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class SourceChangeReportTest(unittest.TestCase):
    def test_builds_owner_readable_markdown_from_review_queue(self) -> None:
        from scripts.source_change_report import build_change_report, format_markdown_report

        queue = {
            "summary": {"needs_review": 2, "changed": 1, "failed": 1, "marker_mismatch": 0},
            "items": [
                {
                    "stem": "sample_2027_undergrad",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "source_url": "https://example.test/sample.pdf",
                    "status": "changed",
                    "old_sha256": "0" * 64,
                    "new_sha256": "1" * 64,
                    "checked_at": "2026-05-26T10:00:00+00:00",
                },
                {
                    "stem": "broken_2027_undergrad",
                    "university": "Broken University",
                    "admission_year": "2027",
                    "source_url": "https://example.test/broken.pdf",
                    "status": "failed",
                    "error": "timeout",
                    "checked_at": "2026-05-26T10:00:00+00:00",
                },
            ],
        }

        report = build_change_report(queue)
        markdown = format_markdown_report(report)

        self.assertEqual(report["summary"]["needs_review"], 2)
        self.assertIn("Source Change Review", markdown)
        self.assertIn("Sample University", markdown)
        self.assertIn("source changed", markdown)
        self.assertIn("confirmed records were not changed", markdown)
        self.assertIn("Broken University", markdown)
        self.assertIn("timeout", markdown)

    def test_reads_default_queue_path(self) -> None:
        from scripts.source_change_report import load_review_queue

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            queue_path = root / "data" / "source_review_queue.json"
            queue_path.parent.mkdir(parents=True)
            queue_path.write_text(json.dumps({"summary": {"needs_review": 0}, "items": []}), encoding="utf-8")

            loaded = load_review_queue(root=root)

        self.assertEqual(loaded["summary"]["needs_review"], 0)


if __name__ == "__main__":
    unittest.main()
