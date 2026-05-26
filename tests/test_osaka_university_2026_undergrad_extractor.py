from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


OSAKA_UNIVERSITY_UNDERGRAD_TEXT = """
2026年度 私費外国人留学生特別入試学生募集要項 大阪大学
Web出願システム登録期間 2025年12月15日(月)10時から2026年1月8日(木)17時。
出願書類受理期間 2026年1月5日(月)から1月9日(金)17時必着。日本留学試験 TOEFL 出願資格 選抜方法。
文学部 人文学科、理学部 生物科学科生命理学コース、医学部 医学科、工学部 応用自然科学科 応用理工学科。
日本留学試験及びTOEFL出願基準点表。文学部は合計300点以上、記述260点以上、TOEFL iBT 48点以上。
理学部生物科学科生命理学コースは物理と化学計2科目、TOEFL iBT 61点以上。
医学部医学科は合計400点以上、基礎科目360点以上、物理、化学、生物から計2科目、出願基準点なし。
工学部は200点以上、25点以上、合計240点以上、物理の他、化学と生物から1科目、出願基準点なし。
TOEFLはTest Date Scoresのみ有効、MyBest Scoresは利用できません。TOEFL iBT Home Edition。
文学部は小論文、口頭試問。医学部医学科は小論文と面接。工学部は数学、理科、口頭試問。
"""


class OsakaUniversity2026UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_osaka_university_baseline(self) -> None:
        from scripts.osaka_university_2026_undergrad_extractor import extract_osaka_university_2026_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_osaka_university_2026_undergrad_records(OSAKA_UNIVERSITY_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "osaka_university_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.osaka_university_2026_undergrad_extractor import extract_osaka_university_2026_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "osaka_university_2026_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_osaka_university_2026_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "osaka_university_2026_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.osaka_university_2026_undergrad_extractor import extract_osaka_university_2026_undergrad_records

        self.assertEqual(extract_osaka_university_2026_undergrad_records("大阪大学 一般選抜 学生募集要項"), [])

    def test_distinguishes_toefl_thresholds_and_no_threshold_notes(self) -> None:
        from scripts.osaka_university_2026_undergrad_extractor import extract_osaka_university_2026_undergrad_records

        records = extract_osaka_university_2026_undergrad_records(OSAKA_UNIVERSITY_UNDERGRAD_TEXT)
        by_id = {record["id"]: record for record in records}

        self.assertIn("48点以上", by_id["osaka-university-2026-literature"]["english_requirement"])
        self.assertIn("61点以上", by_id["osaka-university-2026-science-biology"]["english_requirement"])
        self.assertIn("出願基準点なし", by_id["osaka-university-2026-medicine"]["english_requirement"])
        self.assertIn("物理が必須", by_id["osaka-university-2026-engineering"]["eju_physics"])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "osaka_university.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(OSAKA_UNIVERSITY_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "osaka_university_2026_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "大阪大学")


if __name__ == "__main__":
    unittest.main()
