from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


TOHOKU_UNDERGRAD_TEXT = """
令和8年度（2026年度）特別選抜（総合型選抜）入学試験学生募集要項 私費外国人留学生入試 東北大学
出願受付期間 2026年2月2日(月)から2月5日(木)正午必着。TAO出願サイトは令和8年(2026年)1月3日(土)午前10時予定から。
受験票印刷可能日 2026年2月12日(木)。試験実施 2026年3月10日(火)。合格者発表 2026年3月18日(水)午後5時。
入学手続期間 2026年3月24日(火)から3月27日(金)必着。入学時期 2026年4月。
募集人員 文学部 人文社会学科 若干人、医学部 医学科、工学部、農学部 生物生産科学科、応用生物化学科。
出願資格 日本国籍を有しない者で、在留資格が留学である者又は入学時に留学の在留資格を取得見込みの者。
日本国との多重国籍者及び日本国の永住許可を得ている者は出願できません。
出願書類 入学志願書 写真票 高等学校等の卒業証明書 成績証明書 日本留学試験成績通知書 TOEFL TESTのスコアシート 旅券の写し 住民票 入学検定料。
出願要件 2025年度(令和7年度)日本留学試験 6月実施分又は11月実施分。
文学部は日本語380点以上、基礎学力290点以上。医学部医学科は日本語380点以上、基礎学力350点以上。
工学部は日本語270点以上、基礎学力320点以上。農学部は日本語270点以上、基礎学力260点以上。
文系の試験科目は数学コース1、日本語、総合科目。理系の試験科目は数学コース2、日本語、理科は物理、化学、生物から2科目自由選択。
工学部は物理、化学の2科目。2024年3月1日以降にTOEFL iBT TESTを受験し、その得点が79点以上。
選抜方法 出願書類、日本留学試験、本学が実施する学力試験及び面接試験の結果を総合して行います。
文学部、医学部医学科、工学部は学力試験を実施しません。農学部は数学の学力試験を9:30から11:00、面接試験を13:00から実施。
"""


class Tohoku2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_tohoku_baseline(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tohoku_2026_undergrad_extractor import extract_tohoku_2026_undergrad_records

        records = extract_tohoku_2026_undergrad_records(TOHOKU_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "tohoku_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.tohoku_2026_undergrad_extractor import extract_tohoku_2026_undergrad_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "tohoku_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_tohoku_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "tohoku_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.tohoku_2026_undergrad_extractor import extract_tohoku_2026_undergrad_records

        self.assertEqual(extract_tohoku_2026_undergrad_records("東北大学 一般選抜 入学者選抜要項"), [])

    def test_distinguishes_engineering_and_agriculture_science_rules(self) -> None:
        from scripts.tohoku_2026_undergrad_extractor import extract_tohoku_2026_undergrad_records

        records = extract_tohoku_2026_undergrad_records(TOHOKU_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("物理、化学の2科目", by_id["tohoku-2026-engineering"]["eju_physics"])
        self.assertIn("物理、化学、生物から2科目", by_id["tohoku-2026-agriculture"]["eju_biology"])
        self.assertIn("79点以上", by_id["tohoku-2026-medicine"]["english_requirement"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "tohoku.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(TOHOKU_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "tohoku_2026_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "東北大学")


if __name__ == "__main__":
    unittest.main()
