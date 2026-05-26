from __future__ import annotations

import json
import unittest
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
