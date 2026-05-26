from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


HOKKAIDO_UNDERGRAD_TEXT = """
令和7年12月25日公表
令和9(2027)年度私費外国人留学生（学部）入試基本方針
1 学部・学科等の募集人員等 文学部 教育学部 法学部 経済学部 理学部 医学部医学科 工学部 農学部
2 選抜日程 インターネット出願登録および検定料支払い期間 令和8(2026)年9月7日(月)10時から
令和8(2026)年9月17日(木)17時まで。出願期間（出願書類の郵送）令和8(2026)年9月14日(月)から
令和8(2026)年9月18日(金)17時まで（期間内必着）。第1次選考結果発表 令和8(2026)年10月27日(火)16時予定。
第2次選考日 令和8(2026)年11月15日(日)。合格発表日 令和8(2026)年12月8日(火)16時予定。
入学手続期間 令和8(2026)年12月8日(火)から令和8(2026)年12月14日(月)17時まで。
3 出願資格及び要件 日本の国籍を有しない者、かつ、日本国の永住許可を得ていない者。
外国において学校教育における12年の課程を修了した者及び令和9(2027)年3月31日までに修了見込みの者。
日本留学試験は令和6(2024)年11月、令和7(2025)年6月、令和7(2025)年11月、令和8(2026)年6月。
医学部医学科は日本語385点以上、基礎科目340点以上、TOEFL-iBT 79点以上又はTOEIC L&R 750点以上。
農学部は日本語340点以上、基礎科目300点以上。上記以外の募集単位は日本語270点以上、基礎科目265点以上。
4 選抜方法 文学部は課題論文、面接、英語TOEFL-iBT。工学部は面接、英語能力試験の成績通知書等。
農学部は課題論文、面接、英語能力試験の成績通知書等。
別表 私費外国人留学生入試における日本留学試験の指定科目 文学部 日本語 総合科目 数学コース1又はコース2。
医学部医学科 日本語 理科 物理、化学 数学コース2。工学部 応用理工系学科 情報エレクトロニクス学科 機械知能工学科 環境社会工学科
化学、生物から1科目と物理、又は物理、化学、数学コース2。農学部 物理、化学、生物から2科目、数学コース2。
"""


class Hokkaido2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_hokkaido_baseline(self) -> None:
        from scripts.hokkaido_2027_undergrad_extractor import extract_hokkaido_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_hokkaido_2027_undergrad_records(HOKKAIDO_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "hokkaido_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.hokkaido_2027_undergrad_extractor import extract_hokkaido_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "hokkaido_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_hokkaido_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "hokkaido_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.hokkaido_2027_undergrad_extractor import extract_hokkaido_2027_undergrad_records

        self.assertEqual(extract_hokkaido_2027_undergrad_records("北海道大学 一般選抜 学生募集要項"), [])

    def test_distinguishes_medicine_numeric_english_requirement(self) -> None:
        from scripts.hokkaido_2027_undergrad_extractor import extract_hokkaido_2027_undergrad_records

        records = extract_hokkaido_2027_undergrad_records(HOKKAIDO_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("79点以上", by_id["hokkaido-2027-medicine"]["english_requirement"])
        self.assertIn("750点以上", by_id["hokkaido-2027-medicine"]["english_requirement"])
        self.assertIn("TOEFL-iBT", by_id["hokkaido-2027-literature"]["english_requirement"])
        self.assertIn("IELTS", by_id["hokkaido-2027-engineering"]["english_requirement"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "hokkaido.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(HOKKAIDO_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "hokkaido_2027_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "北海道大学")


if __name__ == "__main__":
    unittest.main()
