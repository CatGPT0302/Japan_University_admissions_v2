from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


TOKYO_METROPOLITAN_UNDERGRAD_TEXT = """
2026年度 特別選抜（私費外国人留学生入試）学生募集要項 東京都立大学
出願期間 2025年12月4日から12月8日。第1次選抜結果発表日 2026年2月11日。第2次選抜日 2026年2月25日 2月26日 3月3日。
日本留学試験 TOEFL 出願期間 別表4。人文社会学部 人間社会学科 人文学科、法学部 法学科、理学部 物理学科、
システムデザイン学部 機械システム工学科。出願資格は外国人で12年の課程を修了した者。
人文社会学部、法学部は日本語、総合科目、数学コース指定なし。理学部物理学科は日本語、理科は物理、化学、数学コース2。
機械システム工学科は日本語、理科は物理指定、化学、生物から1科目選択、数学コース2。
TOEFL iBT、IELTS、TOEIC L&R/S&W。自宅受験版のスコアは認めない。Test Dateスコアのみ有効。MyBestスコアは活用しない。
小論文、地理歴史、数学、理科、面接、口頭試問。
"""


class TokyoMetropolitan2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_baseline(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tokyo_metropolitan_2026_undergrad_extractor import extract_tokyo_metropolitan_2026_undergrad_records

        records = extract_tokyo_metropolitan_2026_undergrad_records(TOKYO_METROPOLITAN_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "tokyo_metropolitan_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tokyo_metropolitan_2026_undergrad_extractor import extract_tokyo_metropolitan_2026_undergrad_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "tokyo_metropolitan_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_tokyo_metropolitan_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "tokyo_metropolitan_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.tokyo_metropolitan_2026_undergrad_extractor import extract_tokyo_metropolitan_2026_undergrad_records

        self.assertEqual(extract_tokyo_metropolitan_2026_undergrad_records("東京都立大学 一般選抜 学生募集要項"), [])

    def test_distinguishes_english_test_options(self) -> None:
        from scripts.tokyo_metropolitan_2026_undergrad_extractor import extract_tokyo_metropolitan_2026_undergrad_records

        records = extract_tokyo_metropolitan_2026_undergrad_records(TOKYO_METROPOLITAN_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("TOEFL iBT", by_id["tokyo-metropolitan-2026-humanities"]["english_requirement"])
        self.assertIn("IELTS", by_id["tokyo-metropolitan-2026-physics"]["english_requirement"])
        self.assertIn("TOEIC L&R/S&W", by_id["tokyo-metropolitan-2026-mechanical"]["english_requirement"])
        self.assertIn("自宅受験版", by_id["tokyo-metropolitan-2026-mechanical"]["english_requirement"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "tokyo_metropolitan.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(TOKYO_METROPOLITAN_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tokyo_metropolitan_2026_undergrad_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 4)
            self.assertEqual(payload["records"][0]["university"], "東京都立大学")


if __name__ == "__main__":
    unittest.main()
