from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


OSAKA_METROPOLITAN_UNDERGRAD_TEXT = """
大阪公立大学 2027年度 私費外国人留学生特別選抜 入試要項
現代システム科学域 知識情報システム学類 出願期間 2026年10月5日(月)から10月8日(木)
選抜期日 2026年11月21日(土) 合格者発表日 2026年12月4日(金)
日本留学試験 日本語 読解、聴解・聴読解、記述。理科は物理、化学、生物から2科目。数学コース2。
知識情報システム学類は日本語270点以上、理科120点以上、数学120点以上。
文学部・法学部・経済学部は出願期間 2026年12月16日(水)から12月21日(月)。
法学部は選抜期日 2027年2月25日(木)、合格者発表日 2027年3月9日(火)。
法学部は日本留学試験、個別学力検査(外国語、作文)、口述試験、出願書類を総合して判定。
法学部はEJU日本語、総合科目、数学コース1で合計600点以上。
農学部 応用生物科学科 出願期間 2026年12月16日(水)から12月21日(月)。
農学部は選抜期日 2027年2月26日(金)、合格者発表日 2027年3月9日(火)。
農学部は日本語270点以上、理科は物理・化学・生物から2科目、数学コース2。
農学部応用生物科学科はTOEFL iBT 2026年1月20日以前のスコア71点以上、以降はバンドスコア4以上。
出願できる者は日本国籍を有しない者で、外国において学校教育における12年の課程を修了した者。
出願に関する詳細は7月以降に公表予定の2027年度学生募集要項を必ず確認すること。
"""


class OsakaMetropolitan2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_osaka_metropolitan_baseline(self) -> None:
        from scripts.osaka_metropolitan_2027_undergrad_extractor import extract_osaka_metropolitan_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_osaka_metropolitan_2027_undergrad_records(OSAKA_METROPOLITAN_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "osaka_metropolitan_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.osaka_metropolitan_2027_undergrad_extractor import extract_osaka_metropolitan_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "osaka_metropolitan_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_osaka_metropolitan_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "osaka_metropolitan_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.osaka_metropolitan_2027_undergrad_extractor import extract_osaka_metropolitan_2027_undergrad_records

        self.assertEqual(extract_osaka_metropolitan_2027_undergrad_records("大阪公立大学 一般選抜 入試要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "osaka_metropolitan.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(OSAKA_METROPOLITAN_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "osaka_metropolitan_2027_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "大阪公立大学")


if __name__ == "__main__":
    unittest.main()
