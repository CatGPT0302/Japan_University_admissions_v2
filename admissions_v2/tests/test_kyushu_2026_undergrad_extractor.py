from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


KYUSHU_UNDERGRAD_TEXT = """
令和8年度（2026年度）学生募集要項 私費外国人留学生入試（4月入学） 九州大学
出願期間 2025年11月4日から11月14日17時必着。Web入力及び入学検定料の支払は2025年10月27日から11月7日まで。
日本国以外の国籍を有する者、日本国の永住許可を得ていない者、外国において学校教育における12年の課程を修了した者。
日本留学試験 TOEFL IELTS 入学者選抜方法。
文学部 法学部 日本語 総合科目 数学コース1。
経済学部 経済工学科 日本語 数学コース2 理科2科目 物理 化学 生物。
医学部 医学科 日本語350点以上 数学コース2 理科2科目 合計360点以上。
工学部 日本語300点以上 数学コース2 物理 化学。
TOEFL iBT Home Edition IELTS IELTS Online ケンブリッジ英検 MyBest。
身上記録書 卒業証明書 成績証明書 日本留学試験 パスポート。
入学者の選抜はTOEFL等の成績証明書 日本留学試験 日本語試験 出願書類 面接。
理学部 工学部 芸術工学部を除く。2月26日 日本語試験 2月27日 面接。
"""


class Kyushu2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_baseline(self) -> None:
        from scripts.kyushu_2026_undergrad_extractor import extract_kyushu_2026_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_kyushu_2026_undergrad_records(KYUSHU_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "kyushu_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.kyushu_2026_undergrad_extractor import extract_kyushu_2026_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "kyushu_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_kyushu_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "kyushu_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.kyushu_2026_undergrad_extractor import extract_kyushu_2026_undergrad_records

        self.assertEqual(extract_kyushu_2026_undergrad_records("九州大学 一般選抜 学生募集要項"), [])

    def test_distinguishes_eju_rules(self) -> None:
        from scripts.kyushu_2026_undergrad_extractor import extract_kyushu_2026_undergrad_records

        records = extract_kyushu_2026_undergrad_records(KYUSHU_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("数学コース1", by_id["kyushu-2026-literature"]["eju_math"])
        self.assertIn("理科2科目選択", by_id["kyushu-2026-economics-engineering"]["eju_physics"])
        self.assertIn("350点以上", by_id["kyushu-2026-medicine"]["eju_japanese"])
        self.assertIn("物理を必須", by_id["kyushu-2026-engineering"]["eju_physics"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "kyushu.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(KYUSHU_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "kyushu_2026_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "九州大学")


if __name__ == "__main__":
    unittest.main()
