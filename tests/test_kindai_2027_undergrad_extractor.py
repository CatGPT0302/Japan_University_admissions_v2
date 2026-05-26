from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


KINDAI_UNDERGRAD_TEXT = """
近畿大学 2027年度【学部】外国人留学生入学試験要項
外国人留学生入学試験は、本学への入学を希望する外国人留学生を対象として行われるものです。
選考方法は出願書類、日本留学試験（EJU）の成績、口頭試問結果、学部独自試験を総合して合否を判定します。
利用できるEJU成績は前期入試2025年第2回または2026年度第1回、後期入試2026年第1回または第2回。
前期入試は2026年8月24日から8月27日、国内居住者は消印有効、国外居住者は2026年8月31日必着。試験日2026年10月10日、合格発表2026年11月9日。
後期入試は2027年1月8日から1月14日、試験日2027年2月20日、合格発表2027年3月9日。
出願資格は外国籍、外国において12年目の課程を修了、2027年3月31日までに18歳に達する者、前期は在留資格「留学」を有する者または入学時に取得できる者、後期は出願時に在留資格「留学」を有する者。
出願書類は出願確認票、入学願書、住民票の写しまたはパスポートのコピー、日本留学試験（EJU）成績確認書、卒業証明書、CSSD証明書、英語能力証明書。
法学部は日本語（記述を含む）と総合科目、口頭試問10:30。EJU日本語が320点以上、総合科目が140点以上。
建築学部は日本語、数学コース2、理科、出題言語は日本語と英語いずれか選択。実技試験（デッサン）10:00-11:00 100点、口頭試問11:20。
農学部は日本語、理科、口頭試問11:00、情報学部・農学部は指定の英語能力証明書を提出できる者。
入学手続は前期第一次2026年11月9日から11月27日、第二次2026年11月9日から2027年1月13日。後期は2027年3月9日から3月15日。
"""


class Kindai2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_kindai_baseline(self) -> None:
        from scripts.kindai_2027_undergrad_extractor import extract_kindai_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_kindai_2027_undergrad_records(KINDAI_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "kindai_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_distinguishes_no_english_requirement_from_unknown(self) -> None:
        from scripts.kindai_2027_undergrad_extractor import extract_kindai_2027_undergrad_records

        records = extract_kindai_2027_undergrad_records(KINDAI_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("要件なし", by_id["kindai-2027-law"]["english_requirement"])
        self.assertIn("要件なし", by_id["kindai-2027-architecture"]["english_requirement"])
        self.assertIn("TOEFL", by_id["kindai-2027-agriculture"]["english_requirement"])

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.kindai_2027_undergrad_extractor import extract_kindai_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "kindai_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_kindai_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "kindai_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.kindai_2027_undergrad_extractor import extract_kindai_2027_undergrad_records

        self.assertEqual(extract_kindai_2027_undergrad_records("近畿大学 一般入試 要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "kindai.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(KINDAI_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "kindai_2027_undergrad_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 3)
            self.assertEqual(payload["records"][0]["university"], "近畿大学")


if __name__ == "__main__":
    unittest.main()
