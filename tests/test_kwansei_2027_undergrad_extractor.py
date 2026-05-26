from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


KWANSEI_UNDERGRAD_TEXT = """
関西学院大学 2027年度 外国人留学生入学試験要項
第Ⅰ期試験（2026年8月出願） 文学部・社会学部・法学部・経済学部・商学部・人間福祉学部・国際学部・教育学部・総合政策学部・理学部・工学部・生命環境学部・建築学部
第Ⅱ期試験（2026年11月出願） 法学部・国際学部・総合政策学部・理学部・工学部・生命環境学部
文学部・社会学部・法学部・経済学部・商学部・人間福祉学部・国際学部・教育学部・総合政策学部・建築学部は第一次審査で書類審査、第二次審査で面接による審査を行います。
文学部・社会学部・人間福祉学部は西宮上ケ原キャンパス、法学部・経済学部・商学部・国際学部・教育学部・総合政策学部・建築学部はオンライン面接。
理学部・工学部・生命環境学部は日本留学試験（EJU）の成績を含めた提出書類による書類審査を行います。試験場での選考はありません。
第Ⅰ期試験 出願期間 2026年8月24日（月）9:00 ～ 8月31日（月）23:00 郵送書類は8月31日（月）必着。
第Ⅱ期試験 出願期間 2026年11月16日（月）9:00 ～ 11月24日（火）23:00 郵送書類は11月24日（火）必着。
第一次審査合格者発表 第Ⅰ期試験 2026年9月25日（金）9:00 第Ⅱ期試験 2027年1月8日（金）9:00。
第二次審査試験日 第Ⅰ期試験 2026年10月10日（土） 第Ⅱ期試験 2027年1月16日（土）。
合格発表 第Ⅰ期試験 2026年11月13日（金）9:00 第Ⅱ期試験 2027年1月22日（金）9:00。
入学手続Ⅰ 第Ⅰ期試験 2026年11月13日（金）～11月27日（金） 第Ⅱ期試験 2027年1月22日（金）～1月29日（金）。
入学手続Ⅱ Web申請 2027年2月15日（月）～3月4日（木）15:00、学費・その他の諸費の納入 2027年2月15日（月）～3月11日（木）。
出願資格は外国籍を有する者、日本の学校教育法にもとづく小学校・中学校・高等学校等に在学した期間が通算4年以内である者、外国において学校教育における12年の課程を修了した者等。
EJUは第Ⅰ期試験で2025年度第2回（11月）または2026年度第1回（6月）、第Ⅱ期試験で2025年度第2回（11月）、2026年度第1回（6月）、2026年度第2回（11月）。
日本語は読解、聴解・聴読解の合計260点以上かつ記述30点以上、第Ⅱ期は265点以上かつ35点以上。ただし上記の点数は目安で必須ではありません。
学部別要件 文学部 日本語 総合科目。法学部 日本語 総合科目 英語能力試験。理学部 日本語 数学コース2 理科いずれか2科目 英語能力試験。
理学部の物理・宇宙学科および化学科を志望する場合は物理・化学の2科目を選択すること。
TOEIC、TOEFL、IELTSのいずれか。スコアの有効期限は第Ⅰ期試験2024年8月24日以降実施分、第Ⅱ期試験2024年11月16日以降実施分。
提出書類一覧 出願資格確認用紙、入学志願調書、卒業証明書、成績証明書、日本留学試験（EJU）成績確認書、英語能力を証明する書類、パスポートコピー貼付用紙、志望理由書、オンライン面接に関する同意書、提出書類チェックシート。
"""


class Kwansei2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_kwansei_baseline(self) -> None:
        from scripts.kwansei_2027_undergrad_extractor import extract_kwansei_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_kwansei_2027_undergrad_records(KWANSEI_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "kwansei_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.kwansei_2027_undergrad_extractor import extract_kwansei_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "kwansei_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_kwansei_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "kwansei_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 3)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.kwansei_2027_undergrad_extractor import extract_kwansei_2027_undergrad_records

        self.assertEqual(extract_kwansei_2027_undergrad_records("関西学院大学 一般選抜 入学試験要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "kwansei.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(KWANSEI_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "kwansei_2027_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "関西学院大学")


if __name__ == "__main__":
    unittest.main()
