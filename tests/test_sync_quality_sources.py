from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class SyncQualitySourcesTest(unittest.TestCase):
    def test_downloads_missing_registered_source(self) -> None:
        from scripts.sync_quality_sources import sync_registered_sources

        registry = {
            "waseda_2027_official": {
                "stem": "waseda_2027_official",
                "source_url": "https://example.test/waseda.pdf",
                "source_candidates": ["data/uploads/waseda_2027_official.pdf"],
                "source_markers": [["Waseda"], ["2027"]],
            }
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("scripts.sync_quality_sources.download_checked_source") as download:
                report = sync_registered_sources(registry=registry, root=root)

        download.assert_called_once_with(
            source_url="https://example.test/waseda.pdf",
            stem="waseda_2027_official",
            markers=[["Waseda"], ["2027"]],
            root=root,
            verify_overview=False,
        )
        self.assertEqual(report["downloaded"], ["waseda_2027_official"])
        self.assertEqual(report["skipped_existing"], [])

    def test_skips_existing_registered_source(self) -> None:
        from scripts.sync_quality_sources import sync_registered_sources

        registry = {
            "waseda_2027_official": {
                "stem": "waseda_2027_official",
                "source_url": "https://example.test/waseda.pdf",
                "source_candidates": ["data/uploads/waseda_2027_official.pdf"],
                "source_markers": [["Waseda"], ["2027"]],
            }
        }

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            cached = root / "data" / "uploads" / "waseda_2027_official.pdf"
            cached.parent.mkdir(parents=True)
            cached.write_bytes(b"%PDF-1.4\nWaseda 2027")

            with patch("scripts.sync_quality_sources.download_checked_source") as download:
                report = sync_registered_sources(registry=registry, root=root)

        download.assert_not_called()
        self.assertEqual(report["downloaded"], [])
        self.assertEqual(report["skipped_existing"], ["waseda_2027_official"])


if __name__ == "__main__":
    unittest.main()
