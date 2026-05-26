from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch


class SourceCacheTest(unittest.TestCase):
    def test_imports_checked_pdf_and_writes_receipt(self) -> None:
        from scripts.source_cache import import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.pdf"
            source.write_bytes(b"%PDF-1.4\nWaseda 2027 official admissions guide")

            receipt = import_checked_source(
                source,
                stem="waseda_2027_official",
                source_url="https://example.test/waseda.pdf",
                markers=[["Waseda University", "Waseda"], ["admission year 2027", "2027"]],
                root=root,
            )

            cached = root / "data" / "uploads" / "waseda_2027_official.pdf"
            receipt_path = root / "quality_sources" / "waseda_2027_official.source.json"

            self.assertTrue(cached.exists())
            self.assertTrue(receipt_path.exists())
            self.assertEqual(receipt["status"], "cached")
            self.assertEqual(receipt["cached_path"], "data/uploads/waseda_2027_official.pdf")
            self.assertEqual(len(receipt["sha256"]), 64)
            self.assertEqual(json.loads(receipt_path.read_text(encoding="utf-8"))["sha256"], receipt["sha256"])

    def test_import_uses_registered_source_candidate_as_canonical_cache_path(self) -> None:
        from scripts.source_cache import import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.pdf"
            source.write_bytes(b"%PDF-1.4\nSample official admissions guide")

            with patch(
                "scripts.source_cache.registered_seed_extractors",
                return_value={"sample": {"source_candidates": ["data/uploads/sample_official.pdf"]}},
            ):
                receipt = import_checked_source(
                    source,
                    stem="sample",
                    source_url="https://example.test/sample.pdf",
                    markers=["Sample"],
                    root=root,
                )

            self.assertEqual(receipt["cached_path"], "data/uploads/sample_official.pdf")
            self.assertTrue((root / "data" / "uploads" / "sample_official.pdf").exists())
            self.assertFalse((root / "data" / "uploads" / "sample.pdf").exists())

    def test_rejects_non_pdf_input(self) -> None:
        from scripts.source_cache import SourceCacheError, import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.txt"
            source.write_text("Waseda 2027 official admissions guide", encoding="utf-8")

            with self.assertRaisesRegex(SourceCacheError, "not_pdf"):
                import_checked_source(
                    source,
                    stem="waseda_2027_official",
                    source_url="https://example.test/waseda.pdf",
                    markers=[["Waseda University", "Waseda"], ["admission year 2027", "2027"]],
                    root=root,
                )

    def test_rejects_pdf_without_required_markers(self) -> None:
        from scripts.source_cache import SourceCacheError, import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.pdf"
            source.write_bytes(b"%PDF-1.4\nunrelated university 2027")

            with self.assertRaisesRegex(SourceCacheError, "marker_mismatch"):
                import_checked_source(
                    source,
                    stem="waseda_2027_official",
                    source_url="https://example.test/waseda.pdf",
                    markers=[["Waseda University", "Waseda"], ["admission year 2027", "2027"]],
                    root=root,
                )

    def test_can_attach_quality_overview_after_import(self) -> None:
        from scripts.source_cache import import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.pdf"
            source.write_bytes(b"%PDF-1.4\nWaseda 2027 official admissions guide")

            with (
                patch(
                    "scripts.source_cache.build_quality_overview",
                    return_value={"overall_status": "needs_owner_action"},
                ) as build_overview,
                patch(
                    "scripts.source_cache.format_owner_summary",
                    return_value="status: needs_owner_action\nnext: add_local_source_pdf",
                ) as format_summary,
            ):
                receipt = import_checked_source(
                    source,
                    stem="waseda_2027_official",
                    source_url="https://example.test/waseda.pdf",
                    markers=[["Waseda University", "Waseda"], ["admission year 2027", "2027"]],
                    root=root,
                    verify_overview=True,
                )

            build_overview.assert_called_once()
            format_summary.assert_called_once_with({"overall_status": "needs_owner_action"})
            self.assertEqual(receipt["quality_overview_status"], "needs_owner_action")
            self.assertIn("next: add_local_source_pdf", receipt["quality_overview_summary"])

    def test_downloads_checked_source_with_browser_headers(self) -> None:
        from scripts.source_cache import download_checked_source

        class FakeResponse:
            content = b"%PDF-1.4\nWaseda 2027 official admissions guide"

            def raise_for_status(self) -> None:
                return None

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            with patch("scripts.source_cache.requests.get", return_value=FakeResponse()) as request_get:
                receipt = download_checked_source(
                    source_url="https://example.test/waseda.pdf",
                    stem="waseda_2027_official",
                    markers=[["Waseda"], ["2027"]],
                    root=root,
                )

            request_get.assert_called_once()
            _url, kwargs = request_get.call_args
            self.assertIn("Mozilla/5.0", kwargs["headers"]["User-Agent"])
            self.assertEqual(kwargs["timeout"], 60)
            self.assertEqual(receipt["status"], "cached")
            self.assertTrue((root / "data" / "uploads" / "waseda_2027_official.pdf").exists())


if __name__ == "__main__":
    unittest.main()
