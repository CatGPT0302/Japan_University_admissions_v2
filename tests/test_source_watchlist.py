from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


class SourceWatchlistTest(unittest.TestCase):
    def test_builds_watchlist_from_seed_registry_and_receipts(self) -> None:
        from scripts.source_watchlist import build_source_watchlist

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            (root / "quality_baselines").mkdir(parents=True)
            (root / "quality_sources" / "sample_2027_undergrad.source.json").write_text(
                json.dumps(
                    {
                        "status": "cached",
                        "source_url": "https://example.test/sample.pdf",
                        "cached_path": "data/uploads/sample.pdf",
                        "sha256": "a" * 64,
                        "size_bytes": 123,
                        "checked_at": "2026-05-26T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            (root / "quality_baselines" / "sample_2027_undergrad.expected.json").write_text(
                json.dumps(
                    [
                        {
                            "id": "sample-record",
                            "source_note": "Official sample international admissions guide.",
                        }
                    ]
                ),
                encoding="utf-8",
            )

            watchlist = build_source_watchlist(
                root=root,
                seeds={
                    "sample_2027_undergrad": {
                        "stem": "sample_2027_undergrad",
                        "id": "sample-2027-undergrad",
                        "university": "Sample University",
                        "admission_year": "2027",
                        "source_url": "https://example.test/sample.pdf",
                        "source_candidates": ["data/uploads/sample.pdf"],
                        "source_markers": ["Sample University", ["2027", "2027年度"]],
                    }
                },
            )

        self.assertEqual(len(watchlist), 1)
        item = watchlist[0]
        self.assertEqual(item["stem"], "sample_2027_undergrad")
        self.assertEqual(item["source_type"], "pdf")
        self.assertEqual(item["admission_type"], "international_undergraduate")
        self.assertEqual(item["last_known_sha256"], "a" * 64)
        self.assertEqual(item["cached_path"], "data/uploads/sample.pdf")
        self.assertEqual(item["source_note"], "Official sample international admissions guide.")
        self.assertEqual(item["markers"], ["Sample University", ["2027", "2027年度"]])

    def test_reports_metadata_gaps_without_blocking_watchlist(self) -> None:
        from scripts.source_watchlist import summarize_watchlist

        summary = summarize_watchlist(
            [
                {
                    "stem": "missing-url",
                    "source_url": "",
                    "source_type": "unknown",
                    "last_known_sha256": "",
                    "last_checked_at": "",
                    "source_note": "",
                },
                {
                    "stem": "ok",
                    "source_url": "https://example.test/ok.pdf",
                    "source_type": "pdf",
                    "last_known_sha256": "b" * 64,
                    "last_checked_at": "2026-05-26T00:00:00+00:00",
                    "source_note": "Official source.",
                },
            ]
        )

        self.assertEqual(summary["total"], 2)
        self.assertEqual(summary["by_type"]["pdf"], 1)
        self.assertEqual(summary["metadata_gaps"]["missing_source_url"], 1)
        self.assertEqual(summary["metadata_gaps"]["missing_hash"], 1)
        self.assertEqual(summary["metadata_gaps"]["missing_source_note"], 1)

    def test_reports_sources_that_have_not_been_checked_recently(self) -> None:
        from scripts.source_watchlist import summarize_watchlist

        summary = summarize_watchlist(
            [
                {
                    "stem": "old",
                    "source_url": "https://example.test/old.pdf",
                    "source_type": "pdf",
                    "last_known_sha256": "a" * 64,
                    "last_checked_at": "2026-04-01T00:00:00+00:00",
                    "source_note": "Official source.",
                },
                {
                    "stem": "fresh",
                    "source_url": "https://example.test/fresh.pdf",
                    "source_type": "pdf",
                    "last_known_sha256": "b" * 64,
                    "last_checked_at": "2026-05-20T00:00:00+00:00",
                    "source_note": "Official source.",
                },
            ],
            now=datetime(2026, 5, 26, tzinfo=timezone.utc),
            stale_days=30,
        )

        self.assertEqual(summary["metadata_gaps"]["stale_last_checked_at"], 1)
        self.assertEqual(summary["stale_check_days"], 30)
        self.assertEqual(summary["oldest_checked_at"], "2026-04-01T00:00:00+00:00")

    def test_watchlist_report_marks_each_source_maintenance_status(self) -> None:
        from scripts.source_watchlist import build_watchlist_report

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            (root / "quality_baselines").mkdir(parents=True)
            (root / "quality_sources" / "sample_2027_undergrad.source.json").write_text(
                json.dumps(
                    {
                        "source_url": "https://example.test/sample.pdf",
                        "sha256": "a" * 64,
                        "checked_at": "2026-01-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )

            report = build_watchlist_report(
                root=root,
                seeds={
                    "sample_2027_undergrad": {
                        "stem": "sample_2027_undergrad",
                        "id": "sample-2027-undergrad",
                        "university": "Sample University",
                        "admission_year": "2027",
                        "source_url": "https://example.test/sample.pdf",
                    }
                },
            )

        self.assertIn(report["items"][0]["check_status"], {"recent", "stale"})
        self.assertIsInstance(report["items"][0]["days_since_checked"], int)

    def test_watchlist_report_keeps_failed_check_visible_even_if_recent(self) -> None:
        from scripts.source_watchlist import build_watchlist_report

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            (root / "quality_sources" / "sample_2027_undergrad.source.json").write_text(
                json.dumps(
                    {
                        "source_url": "https://example.test/sample.pdf",
                        "sha256": "a" * 64,
                        "checked_at": "2026-05-26T00:00:00+00:00",
                        "last_check_status": "failed",
                        "last_check_error": "network down",
                    }
                ),
                encoding="utf-8",
            )

            report = build_watchlist_report(
                root=root,
                seeds={
                    "sample_2027_undergrad": {
                        "stem": "sample_2027_undergrad",
                        "id": "sample-2027-undergrad",
                        "university": "Sample University",
                        "admission_year": "2027",
                        "source_url": "https://example.test/sample.pdf",
                    }
                },
            )

        self.assertEqual(report["items"][0]["check_status"], "failed")
        self.assertEqual(report["items"][0]["last_check_error"], "network down")
        self.assertEqual(report["summary"]["metadata_gaps"]["last_check_needs_attention"], 1)


if __name__ == "__main__":
    unittest.main()
