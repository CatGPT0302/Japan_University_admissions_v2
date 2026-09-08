from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


OKAYAMA_UNDERGRAD_TEXT = """
2026年度 私費外国人留学生 選抜 学生募集要項 岡山大学
出願期間 文学部 法学部 経済学部 理学部 医学部 歯学部 薬学部 工学部 2026年1月26日から1月29日。
農学部 農学グローバル入試 2025年11月4日から11月11日。
出願資格 日本国籍を有しない者 外国において学校教育における12年の課程を修了 在留資格。
日本留学試験 入学者選抜方法。
文学部 人文学科 日本語 総合科目 数学コース1又はコース2 合計得点580点以上。
経済学部 経済学科 日本語 総合科目110点以上 数学110点以上。
医学部 医学科 日本語 合計得点760点以上 数学コース2 物理 化学 生物。
工学部 工学科機械システム系 日本語 数学コース2 物理必須 化学 生物。
農学部 農学科 日本語 数学 理科 物理 化学 生物 英語資格・検定試験 課題作文。
TOEFL TOEIC L&R My Best Home Edition。
書類審査 日本語作文 小論文 面接 オンライン面接。
合格者発表 2026年3月7日 2025年12月22日。入学手続 2026年3月18日 2026年1月28日。
"""


class Okayama2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_baseline(self) -> None:
        from scripts.okayama_2026_undergrad_extractor import extract_okayama_2026_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_okayama_2026_undergrad_records(OKAYAMA_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "okayama_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 5)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.okayama_2026_undergrad_extractor import extract_okayama_2026_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "okayama_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_okayama_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "okayama_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 5)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.okayama_2026_undergrad_extractor import extract_okayama_2026_undergrad_records

        self.assertEqual(extract_okayama_2026_undergrad_records("岡山大学 一般選抜 学生募集要項"), [])

    def test_keeps_agriculture_timeline_separate(self) -> None:
        from scripts.okayama_2026_undergrad_extractor import extract_okayama_2026_undergrad_records

        records = extract_okayama_2026_undergrad_records(OKAYAMA_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("2025年11月4日", by_id["okayama-2026-agriculture-global"]["application_period"])
        self.assertIn("2026年1月26日", by_id["okayama-2026-literature"]["application_period"])
        self.assertIn("2026年1月28日", by_id["okayama-2026-agriculture-global"]["enrollment_period"])

    def test_distinguishes_eju_rules(self) -> None:
        from scripts.okayama_2026_undergrad_extractor import extract_okayama_2026_undergrad_records

        records = extract_okayama_2026_undergrad_records(OKAYAMA_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("580点以上", by_id["okayama-2026-literature"]["eju_japanese"])
        self.assertIn("数学110点以上", by_id["okayama-2026-economics"]["eju_math"])
        self.assertIn("760点以上", by_id["okayama-2026-medicine"]["eju_japanese"])
        self.assertIn("物理を必須", by_id["okayama-2026-engineering-mechanical"]["eju_physics"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "okayama.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(OKAYAMA_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "okayama_2026_undergrad_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 5)
            self.assertEqual(payload["records"][0]["university"], "岡山大学")


if __name__ == "__main__":
    unittest.main()
