from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


TOKYO_MARINE_UNDERGRAD_TEXT = """
令和8（2026）年度 私費外国人留学生特別入試 学生募集要項 東京海洋大学
出願期間 2026年1月26日（月）から2月4日（水）17:00 郵送必着。
入学試験日 2026年2月25日（水）。合格発表日 2026年3月9日（月）。
海洋生命科学部 海洋生物資源学科 食品生産科学科 海洋政策文化学科 若干名。
海洋資源環境学部 海洋環境科学科 海洋資源エネルギー学科 若干名。
出願資格 日本国籍を有しない者、外国において学校教育における12年の課程を修了した者、
2025年度日本留学試験 日本語 理科（2科目選択） 数学（コース2） 出題言語は日本語。
英語資格 TOEIC L&R 400点以上 TOEFL iBT 40点以上 IELTS 3.5以上 英検準2級以上 TEAP。
インターネット出願登録、検定料支払いだけでは出願は完了しない。書留速達郵便。直接持参は受け付けない。
入学志願票 英語資格検定証明書 志望理由書 履歴書 日本留学試験 住民票 パスポート。
入試方法等 大学入学共通テストを免除し、個別テスト 面接 日本留学試験 提出書類で判定。
品川キャンパス 10:00-12:00 日本語 外国語 13:30-15:30 数学 理科 16:00 面接。
海洋工学部 海事システム工学科 海洋電子機械工学科 流通情報工学科。
海洋工学部へ出願する者は 日本語 理科（物理・化学） 数学（コース2）を受験。
英語資格・検定試験に係る出願要件は無し。
越中島キャンパス 10:00-12:00 数学 13:30-14:00 外国語 14:30 面接。
"""


class TokyoMarine2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_baseline(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tokyo_marine_2026_undergrad_extractor import extract_tokyo_marine_2026_undergrad_records

        records = extract_tokyo_marine_2026_undergrad_records(TOKYO_MARINE_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "tokyo_marine_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tokyo_marine_2026_undergrad_extractor import extract_tokyo_marine_2026_undergrad_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "tokyo_marine_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_tokyo_marine_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "tokyo_marine_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.tokyo_marine_2026_undergrad_extractor import extract_tokyo_marine_2026_undergrad_records

        self.assertEqual(extract_tokyo_marine_2026_undergrad_records("東京海洋大学 一般選抜 学生募集要項"), [])

    def test_distinguishes_english_requirement_by_faculty_group(self) -> None:
        from scripts.tokyo_marine_2026_undergrad_extractor import extract_tokyo_marine_2026_undergrad_records

        records = extract_tokyo_marine_2026_undergrad_records(TOKYO_MARINE_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("TOEFL iBT 40点以上", by_id["tokyo-marine-2026-marine-bioresources"]["english_requirement"])
        self.assertIn("IELTS 3.5以上", by_id["tokyo-marine-2026-marine-environment"]["english_requirement"])
        self.assertIn("出願要件は無し", by_id["tokyo-marine-2026-marine-engineering"]["english_requirement"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "tokyo_marine.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(TOKYO_MARINE_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tokyo_marine_2026_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "東京海洋大学")


if __name__ == "__main__":
    unittest.main()
