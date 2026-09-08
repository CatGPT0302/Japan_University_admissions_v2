from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


KEIO_MEDICINE_TEXT = """
慶應義塾大学 2027年度 医学部外国人留学生対象 入学試験募集要項
医学部 医学科 若干名
Webエントリー 2026年7月3日（金）10:00～7月14日（火）16:00
出願書類の郵送 2026年7月3日（金）～7月15日（水）
速達・簡易書留 締切日必着
出願資格 学校教育課程12年以上を修めた者、および2027年3月31日までに修める見込みの者
海外の学校教育制度に基づく中学校および高等学校の全期間の課程を修了した者
第1次選考合格発表 2026年9月8日（火）10:00
第2次選考試験日 2026年9月27日（日）
最終合格発表 2026年9月29日（火）10:00
入学手続期間 2026年11月30日（月）～12月11日（金）
第1次選考（書類選考）
第2次選考 総合問題 模擬講義 面接
出願書類チェックリスト 入学志願票 入学志願者調書 志望理由書 エッセイ 成績証明書 推薦状 日本留学試験結果 TOEFL IELTS パスポート
日本留学試験 2024年度第2回（2024年11月実施）から2025年度第2回（2025年11月実施）まで
2026年度第1回（2026年6月実施）
基準点は設けていません
TOEFL iBTもしくはIELTS Academic Module
受験期間 2024年9月1日～2026年6月30日
第2次選考 試験日 9月27日（日） 集合時刻 8:45 9:00～ 信濃町キャンパス
"""


class KeioMedicine2027ExtractorTest(unittest.TestCase):
    def test_extracts_seed_record_that_passes_keio_medicine_baseline(self) -> None:
        from scripts.keio_medicine_2027_extractor import extract_keio_2027_medicine_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_keio_2027_medicine_records(KEIO_MEDICINE_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "keio_2027_medicine.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 1)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_record_from_real_pdf_text(self) -> None:
        from scripts.keio_medicine_2027_extractor import extract_keio_2027_medicine_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "keio_2027_medicine.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_keio_2027_medicine_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "keio_2027_medicine.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 1)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.keio_medicine_2027_extractor import extract_keio_2027_medicine_records

        self.assertEqual(extract_keio_2027_medicine_records("明治大学 2027年度 外国人留学生入学試験"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "keio.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(KEIO_MEDICINE_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "keio_medicine_2027_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 1)
            self.assertEqual(payload["records"][0]["university"], "慶應義塾大学")


if __name__ == "__main__":
    unittest.main()
