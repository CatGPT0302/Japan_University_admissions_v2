from __future__ import annotations

import json
import unittest
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory


class CheckSourceUpdatesTest(unittest.TestCase):
    def _watch_item(self, *, old_hash: str) -> dict:
        return {
            "stem": "sample_2027_undergrad",
            "id": "sample-2027-undergrad",
            "university": "Sample University",
            "admission_year": "2027",
            "admission_type": "international_undergraduate",
            "source_type": "pdf",
            "source_url": "https://example.test/sample.pdf",
            "cached_path": "data/uploads/sample.pdf",
            "last_known_sha256": old_hash,
            "markers": ["Sample University", "2027"],
            "source_note": "Official sample guide.",
        }

    def test_unchanged_source_writes_check_log_without_review_item(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources, content_sha256

        content = b"%PDF-1.4\nSample University 2027 admissions"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = check_watchlist_sources(
                watchlist=[self._watch_item(old_hash=content_sha256(content))],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
            )
            log_lines = (root / "data" / "source_checks.jsonl").read_text(encoding="utf-8").splitlines()
            queue = json.loads((root / "data" / "source_review_queue.json").read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["unchanged"], 1)
        self.assertEqual(report["summary"]["changed"], 0)
        self.assertEqual(len(log_lines), 1)
        self.assertEqual(json.loads(log_lines[0])["status"], "unchanged")
        self.assertEqual(queue["items"], [])

    def test_changed_source_creates_review_queue_item_without_updating_receipt(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources

        changed_content = b"%PDF-1.4\nSample University 2027 admissions changed"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            receipt = root / "quality_sources" / "sample_2027_undergrad.source.json"
            receipt.write_text(json.dumps({"sha256": "0" * 64}), encoding="utf-8")

            report = check_watchlist_sources(
                watchlist=[self._watch_item(old_hash="0" * 64)],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": changed_content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
            )
            queue = json.loads((root / "data" / "source_review_queue.json").read_text(encoding="utf-8"))
            stored_receipt = json.loads(receipt.read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["changed"], 1)
        self.assertEqual(queue["summary"]["needs_review"], 1)
        self.assertEqual(queue["items"][0]["status"], "changed")
        self.assertEqual(queue["items"][0]["stem"], "sample_2027_undergrad")
        self.assertEqual(stored_receipt["sha256"], "0" * 64)
        self.assertEqual(stored_receipt["checked_at"], "2026-05-26T10:00:00+00:00")
        self.assertEqual(stored_receipt["last_check_status"], "changed")
        self.assertNotEqual(stored_receipt["last_check_sha256"], stored_receipt["sha256"])

    def test_changed_html_source_includes_owner_diff_preview(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources, content_sha256

        old_content = "Sample University 2027 出願期間 2026年9月1日から9月10日まで"
        new_content = "Sample University 2027 出願期間 2026年9月5日から9月20日まで"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "data" / "uploads" / "sample.html"
            cached.parent.mkdir(parents=True)
            cached.write_text(old_content, encoding="utf-8")
            item = {
                **self._watch_item(old_hash=content_sha256(old_content.encode("utf-8"))),
                "source_type": "html",
                "source_url": "https://example.test/sample.html",
                "cached_path": "data/uploads/sample.html",
                "markers": ["Sample University", "2027"],
            }

            report = check_watchlist_sources(
                watchlist=[item],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": new_content.encode("utf-8"), "content_type": "text/html"},
                now="2026-05-26T10:00:00+00:00",
            )
            queue = json.loads((root / "data" / "source_review_queue.json").read_text(encoding="utf-8"))

        diff_preview = report["items"][0]["diff_preview"]
        self.assertTrue(diff_preview["has_text_comparison"])
        self.assertIn("9月1日", diff_preview["old_excerpt"][0])
        self.assertIn("9月20日", diff_preview["new_excerpt"][0])
        self.assertEqual(queue["items"][0]["diff_preview"], diff_preview)

    def test_first_check_without_known_hash_enters_review_queue(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources

        content = b"%PDF-1.4\nSample University 2027 admissions"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            receipt = root / "quality_sources" / "sample_2027_undergrad.source.json"
            receipt.write_text(json.dumps({"source_url": "https://example.test/sample.pdf"}), encoding="utf-8")

            report = check_watchlist_sources(
                watchlist=[self._watch_item(old_hash="")],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
            )
            queue = json.loads((root / "data" / "source_review_queue.json").read_text(encoding="utf-8"))
            stored_receipt = json.loads(receipt.read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["first_check"], 1)
        self.assertEqual(report["summary"]["needs_review"], 1)
        self.assertEqual(queue["summary"]["first_check"], 1)
        self.assertEqual(queue["items"][0]["status"], "first_check")
        self.assertEqual(stored_receipt["last_check_status"], "first_check")
        self.assertEqual(stored_receipt["last_check_sha256"], report["items"][0]["new_sha256"])
        self.assertNotIn("sha256", stored_receipt)

    def test_successful_check_refreshes_watchlist_maintenance_time(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources, content_sha256
        from scripts.source_watchlist import build_watchlist_report

        content = b"%PDF-1.4\nSample University 2027 admissions"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            receipt = root / "quality_sources" / "sample_2027_undergrad.source.json"
            receipt.write_text(
                json.dumps(
                    {
                        "source_url": "https://example.test/sample.pdf",
                        "sha256": content_sha256(content),
                        "checked_at": "2026-04-01T00:00:00+00:00",
                    }
                ),
                encoding="utf-8",
            )
            check_watchlist_sources(
                watchlist=[self._watch_item(old_hash=content_sha256(content))],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
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
                now=datetime(2026, 5, 26, 10, tzinfo=timezone.utc),
            )

        self.assertEqual(report["items"][0]["last_checked_at"], "2026-05-26T10:00:00+00:00")
        self.assertEqual(report["items"][0]["check_status"], "recent")

    def test_successful_check_clears_stale_receipt_error(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources, content_sha256

        content = b"%PDF-1.4\nSample University 2027 admissions"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "quality_sources").mkdir(parents=True)
            receipt = root / "quality_sources" / "sample_2027_undergrad.source.json"
            receipt.write_text(
                json.dumps(
                    {
                        "source_url": "https://example.test/sample.pdf",
                        "sha256": content_sha256(content),
                        "checked_at": "2026-04-01T00:00:00+00:00",
                        "last_check_status": "failed",
                        "last_check_error": "old network failure",
                    }
                ),
                encoding="utf-8",
            )

            check_watchlist_sources(
                watchlist=[self._watch_item(old_hash=content_sha256(content))],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
            )
            stored_receipt = json.loads(receipt.read_text(encoding="utf-8"))

        self.assertEqual(stored_receipt["last_check_status"], "unchanged")
        self.assertNotIn("last_check_error", stored_receipt)

    def test_failed_check_is_reported_but_does_not_create_data_change(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources

        def failing_fetcher(_url: str) -> dict:
            raise RuntimeError("network down")

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = check_watchlist_sources(
                watchlist=[self._watch_item(old_hash="0" * 64)],
                root=root,
                fetcher=failing_fetcher,
                now="2026-05-26T10:00:00+00:00",
            )
            queue = json.loads((root / "data" / "source_review_queue.json").read_text(encoding="utf-8"))

        self.assertEqual(report["summary"]["failed"], 1)
        self.assertEqual(report["items"][0]["status"], "failed")
        self.assertEqual(queue["items"][0]["status"], "failed")
        self.assertIn("network down", report["items"][0]["error"])

    def test_marker_mismatch_is_review_item(self) -> None:
        from scripts.check_source_updates import check_watchlist_sources, content_sha256

        content = b"%PDF-1.4\nUnrelated University 2027 admissions"
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = check_watchlist_sources(
                watchlist=[self._watch_item(old_hash=content_sha256(content))],
                root=root,
                fetcher=lambda _url: {"status_code": 200, "content": content, "content_type": "application/pdf"},
                now="2026-05-26T10:00:00+00:00",
            )

        self.assertEqual(report["summary"]["marker_mismatch"], 1)
        self.assertEqual(report["items"][0]["status"], "marker_mismatch")
        self.assertIn("Sample University", report["items"][0]["missing_markers"])


if __name__ == "__main__":
    unittest.main()
