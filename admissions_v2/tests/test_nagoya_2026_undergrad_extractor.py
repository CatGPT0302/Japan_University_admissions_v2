from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


NAGOYA_UNDERGRAD_TEXT = """
2026年度 名古屋大学 私費外国人留学生募集要項
出願資格及び要件 日本留学試験 TOEFL IELTS。
インターネット出願登録期間及び入学検定料払込期間 2025年11月24日から12月4日。
出願期間 2025年12月1日から12月5日15時 郵送必着。
文学部 情報学部 自然情報学科 医学部 医学科 農学部。
日本国籍を有しない者。外国において学校教育における12年の課程を修了。
2024年度第2回又は2025年度第1回 日本留学試験 出題言語 日本語。
文学部 日本語220点以上 総合科目 数学コース1 合計265点以上。
情報学部自然情報学科 日本語300点以上 理科 物理 化学 生物から2科目選択 数学コース2 合計265点以上。
医学部医学科 日本語420点以上 理科 物理 化学 生物から2科目選択 数学コース2 合計380点以上。
農学部 日本語300点以上 理科 物理 化学 生物から2科目選択 数学コース2 合計300点以上。
TOEFL iBT 61点以上 IELTS 5.5 TOEFL iBT 90点以上 My Best Home Edition TOEFL-ITPは利用できない。
選抜方法 小論文 面接 オンライン面接 筆記 生命科学 口頭試問。
合格者発表 2026年2月11日12時。入学手続 2026年2月11日から2月18日15時。
"""


class Nagoya2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_baseline(self) -> None:
        from scripts.nagoya_2026_undergrad_extractor import extract_nagoya_2026_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_nagoya_2026_undergrad_records(NAGOYA_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "nagoya_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.nagoya_2026_undergrad_extractor import extract_nagoya_2026_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "nagoya_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_nagoya_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "nagoya_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.nagoya_2026_undergrad_extractor import extract_nagoya_2026_undergrad_records

        self.assertEqual(extract_nagoya_2026_undergrad_records("名古屋大学 一般選抜 学生募集要項"), [])

    def test_does_not_create_engineering_record_when_guide_lists_no_engineering_recruitment(self) -> None:
        from scripts.nagoya_2026_undergrad_extractor import extract_nagoya_2026_undergrad_records

        records = extract_nagoya_2026_undergrad_records(NAGOYA_UNDERGRAD_TEXT)
        self.assertNotIn("工学部", {record["faculty"] for record in records})

    def test_distinguishes_eju_and_english_thresholds(self) -> None:
        from scripts.nagoya_2026_undergrad_extractor import extract_nagoya_2026_undergrad_records

        records = extract_nagoya_2026_undergrad_records(NAGOYA_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("220点以上", by_id["nagoya-2026-literature"]["eju_japanese"])
        self.assertIn("300点以上", by_id["nagoya-2026-informatics-natural"]["eju_japanese"])
        self.assertIn("420点以上", by_id["nagoya-2026-medicine"]["eju_japanese"])
        self.assertIn("TOEFL iBT 90点以上", by_id["nagoya-2026-medicine"]["english_requirement"])
        self.assertIn("My Bestスコアを利用しない", by_id["nagoya-2026-agriculture"]["english_requirement"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "nagoya.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(NAGOYA_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "nagoya_2026_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "名古屋大学")


if __name__ == "__main__":
    unittest.main()
