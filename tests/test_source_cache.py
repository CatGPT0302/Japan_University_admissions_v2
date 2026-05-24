from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


class SourceCacheTest(unittest.TestCase):
    def test_imports_checked_pdf_and_writes_receipt(self) -> None:
        from scripts.source_cache import import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.pdf"
            source.write_bytes("%PDF-1.4\n早稲田大学 2027年度 外国学生".encode("utf-8"))

            receipt = import_checked_source(
                source,
                stem="waseda_2027_official",
                source_url="https://example.test/waseda.pdf",
                markers=[["Waseda", "早稲田大学"], ["2027", "2027年度"]],
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

    def test_rejects_non_pdf_input(self) -> None:
        from scripts.source_cache import SourceCacheError, import_checked_source

        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "downloaded.txt"
            source.write_text("早稲田大学 2027年度", encoding="utf-8")

            with self.assertRaisesRegex(SourceCacheError, "not_pdf"):
                import_checked_source(
                    source,
                    stem="waseda_2027_official",
                    source_url="https://example.test/waseda.pdf",
                    markers=[["Waseda", "早稲田大学"], ["2027", "2027年度"]],
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
                    markers=[["Waseda", "早稲田大学"], ["2027", "2027年度"]],
                    root=root,
                )


if __name__ == "__main__":
    unittest.main()
