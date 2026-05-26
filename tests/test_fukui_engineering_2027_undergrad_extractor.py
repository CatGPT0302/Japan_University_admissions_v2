from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


FUKUI_ENGINEERING_TEXT = """
2027（令和９）年度 福井大学 工学部 私費外国人留学生選抜 学生募集要項（総合型選抜）
日程の概要 出願期間 2026（令和８）年 10 月 13 日(火) ～ 10 月 20 日(火) 選考日 2026（令和８）年 10 月 30 日(金) 入学手続期間 2026（令和８）年 12 月 14 日(月) ～ 12 月 25 日(金) 合格者発表 2026（令和８）年 11 月 30 日(月)
募集人員 工学部 機械・システム工学科 各学科 若干名 電気電子情報工学科 建築・都市環境工学科 物質・生命化学科 応用物理学科
出願資格 日本国籍を有しない者 12 年の課程を修了 2027 年 3 月 31 日までに修了見込み 2025 年度又は 2026 年度 日本留学試験 学部で指定する科目 2026 年度の日本留学試験の成績を利用する場合は第 1 回のみ 2025 年 1 月以降に実施された TOEFL を受験 TOEFL iBT Home Edition も認める 留学の在留資格
出願期間・方法 2026 年 10 月 13 日（火）～10 月 20 日（火）16 時までに必着 郵送 簡易書留速達 2026 年 10 月 19 日（月）までの発信局日付印のある簡易書留速達郵便に限り受理 持参による出願は認めません
出願書類 入学志願票 誓約書 受験票・写真票 出願確認票 出願資格証明書及び成績証明書 日本留学試験の受験票（写） TOEFL のスコア票 Test Taker Score Report Official Score Report 住民票等 あて名票 返信用封筒 出願用封筒
選抜方法等 2026 年 10 月 30 日（金） 福井大学 文京キャンパス 13:00 ～ 13:15 受付 13:30 ～ 面接及び口頭試問 海外居住者でオンライン希望者はオンラインで実施
選抜方法 日本留学試験 TOEFL 本学が実施する面接等の成績及び出願書類を総合して行います 日本語 理科 物理・化学・生物から２科目 総合科目 × 数学 コース２ TOEFL ○ 面接及び口頭試問 日本留学試験の出題言語は日本語に限ります
合格者発表 2026 年 11 月 30 日（月）10 時 入学手続 2026 年 12 月 14 日（月）～12 月 25 日（金）16 時までに必着 入学料 282,000 円 授業料 前期分 267,900 円 年額 535,800 円
"""


class FukuiEngineering2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_fukui_baseline(self) -> None:
        from scripts.fukui_engineering_2027_undergrad_extractor import extract_fukui_engineering_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_fukui_engineering_2027_undergrad_records(FUKUI_ENGINEERING_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "fukui_engineering_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 5)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.fukui_engineering_2027_undergrad_extractor import extract_fukui_engineering_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "fukui_engineering_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_fukui_engineering_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "fukui_engineering_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 5)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.fukui_engineering_2027_undergrad_extractor import extract_fukui_engineering_2027_undergrad_records

        self.assertEqual(extract_fukui_engineering_2027_undergrad_records("福井大学 工学部 一般選抜 募集要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "fukui.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(FUKUI_ENGINEERING_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "fukui_engineering_2027_undergrad_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 5)
            self.assertEqual(payload["records"][0]["university"], "福井大学")


if __name__ == "__main__":
    unittest.main()
