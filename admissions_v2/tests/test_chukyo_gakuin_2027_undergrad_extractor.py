from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


CHUKYO_GAKUIN_UNDERGRAD_TEXT = """
中京学院大学 2027年度 学生募集要項 外国人留学生選抜 経営学部・看護学部
経営学部・経営学科 40名、看護学部・看護学科 若干名。
外国籍を有する者で、外国において日本の高等学校に相当する学校を卒業、または12年以上の学校教育を修了し、その国において大学入学資格を有する者。
経営学部は日本語能力としてB2相当、例としてJLPTの場合はN2以上。看護学部はB2以上。
指定校推薦選抜は在籍学校での出席率92%以上、日本語能力を示す公的試験の結果がB2相当。
一般選抜は書類審査、面接、日本語テスト。指定校推薦は日本語テスト免除。
募集期間は6/1から募集開始。締切は1回目7/8、2回目8/12、3回目9/9、4回目10/7、5回目11/11、6回目12/9、いずれも必着。
試験日は7月16日、8月20日、9月17日、10月15日、11月19日、12月17日。
合格発表は7月24日、8月28日、9月25日、10月23日、11月27日、12月24日に発送。
手続き締切日は10月23日、11月27日、12月24日、1月15日。年明け以降は募集状況を見ながら判断し、出願前に必ず問い合わせや事前の相談をすること。
提出書類は入学志願票、留学生学歴等記載、志望理由書、経費支弁書、推薦書、入学金免除申請書、写真2枚、高等学校の卒業証明書、成績証明書、日本国内で在籍している学校の証明書、出願資格を満たす証明、日本語能力がわかる公的証明書、パスポートコピー、在留カードコピー。
選抜試験時間は13:00から15:00予定。入学手続きは期日までに入学手続金を納入し、入学手続書類を提出すること。入学許可書を発行。
"""


class ChukyoGakuin2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_chukyo_gakuin_baseline(self) -> None:
        from scripts.chukyo_gakuin_2027_undergrad_extractor import extract_chukyo_gakuin_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_chukyo_gakuin_2027_undergrad_records(CHUKYO_GAKUIN_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "chukyo_gakuin_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 2)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.chukyo_gakuin_2027_undergrad_extractor import extract_chukyo_gakuin_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "chukyo_gakuin_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_chukyo_gakuin_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "chukyo_gakuin_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 2)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.chukyo_gakuin_2027_undergrad_extractor import extract_chukyo_gakuin_2027_undergrad_records

        self.assertEqual(extract_chukyo_gakuin_2027_undergrad_records("中京学院大学 一般選抜 学生募集要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "chukyo_gakuin.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(CHUKYO_GAKUIN_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "chukyo_gakuin_2027_undergrad_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 2)
            self.assertEqual(payload["records"][0]["university"], "中京学院大学")


if __name__ == "__main__":
    unittest.main()
