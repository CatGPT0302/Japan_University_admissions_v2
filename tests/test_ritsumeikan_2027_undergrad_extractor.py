from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


RITSUMEIKAN_UNDERGRAD_TEXT = """
立命館大学 2027年度 外国人留学生入学試験 前期実施 後期実施 入学試験要項
出願期間 前期実施 2026年8月18日10:00から8月28日23:00、後期実施 2026年11月9日10:00から11月16日23:00。
第1次選考合格発表日 前期2026年9月25日、後期2026年12月25日。第2次選考日は前期2026年10月3日または10月4日、後期2027年1月9日または1月10日。
第2次選考合格発表日 前期2026年10月19日、後期2027年1月20日。第1次入学手続期間は前期2026年10月19日から11月2日、後期2027年1月20日から2月3日。第2次入学手続期間は2027年3月9日から3月18日。
経営学部は1段階選抜で第2次選考は行いません。
出願資格は外国籍を有する者、2027年3月31日までに12年の課程を修了した者、日本の小学校・中学校・高等学校等に在学した期間が通算3年以内である者。
EJUは前期実施が2025年度第2回または2026年度第1回、後期実施が2026年度第1回または2026年度第2回。
法学部と経営学部は日本語（記述問題含む）と総合科目または数学コース1またはコース2のいずれか1科目。理工学部は日本語、数学コース2、理科（物理・化学の2科目）。
前期実施は日本語読解・聴解・聴読解280点以上、記述35点以上。理工学部は250点以上、30点以上。後期実施は目安点で目安点以上を取得していなくても出願要件を満たします。
経営学部は英語外部資格試験が必要。英検、TOEFL iBT、TOEIC Listening & Reading、IELTS、TEAP、Duolingo English Test。TOEFL Home Edition、TOEIC IP、IELTS Onlineは対象外。
提出書類は高等学校卒業証明書、成績証明書、志望理由書、パスポート、写真、日本留学試験成績確認書、英語外部資格試験の成績証明書。
全学部（経営学部を除く）は第1次選考が日本留学試験の成績、第2次選考が日本留学試験の成績と個人面接の総合評価。経営学部は日本留学試験の成績と出願書類の総合評価。
面接はすべて日本語。理工学部では理系の素養を確認するために口頭試問を行います。
法学部は前期10月3日、後期1月9日。理工学部は前期10月4日、後期1月10日。国内はキャンパスで対面面接、国外は自宅等でオンライン面接。
"""


class Ritsumeikan2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_ritsumeikan_baseline(self) -> None:
        from scripts.ritsumeikan_2027_undergrad_extractor import extract_ritsumeikan_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_ritsumeikan_2027_undergrad_records(RITSUMEIKAN_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "ritsumeikan_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.ritsumeikan_2027_undergrad_extractor import extract_ritsumeikan_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "ritsumeikan_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_ritsumeikan_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "ritsumeikan_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.ritsumeikan_2027_undergrad_extractor import extract_ritsumeikan_2027_undergrad_records

        self.assertEqual(extract_ritsumeikan_2027_undergrad_records("立命館大学 一般選抜 入学試験要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "ritsumeikan.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(RITSUMEIKAN_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "ritsumeikan_2027_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "立命館大学")


if __name__ == "__main__":
    unittest.main()
