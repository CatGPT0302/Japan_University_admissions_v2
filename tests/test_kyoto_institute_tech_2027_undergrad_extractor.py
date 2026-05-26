from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]


KIT_UNDERGRAD_TEXT = """
2027 年度 京都工芸繊維大学 私費外国人留学生入試 学生募集要項
私費外国人留学生募集について 日本の大学で教育を受ける目的をもって入国し、私費により本学に入学を希望する外国人を対象として、次のとおり入学者を特別に選抜します。
募集人員 応用生物学域 応用生物学課程 若干名 物質・材料科学域 応用化学課程 若干名 設計工学域 電子システム工学課程 若干名 情報工学課程 若干名 機械工学課程 若干名 デザイン科学域 デザイン・建築学課程 建築コース 若干名 デザインコース 若干名
日本留学試験 2025 年 11 月又は 2026 年 6 月実施 日本語 数学 コース 2 理科 物理 化学 生物
応用生物学課程 ○ ○ 物理･化学･生物から 2 科目を選択
応用化学課程 ○ ○ ○ ○ ―
電子システム工学課程 ○ ○ ○ 化学・生物から 1 科目を選択
デザイン・建築学課程 建築コース ○ ○ 物理･化学･生物から 1 科目を選択 デザインコース ○ ○ 物理･化学･生物から 1 科目を選択
日本語 280 点以上 数学（コース 2）120 点以上 TOEFL Home Edition を含む iBT テストのみ可 2024 年 8 月から 2026 年 6 月の受験分まで有効 TOEFL-ITP は認めません。
出願書類 入学願書 履歴書 日本留学試験受験票（写） TOEFLiBT スコアカード Test Taker Score Report 出願資格の区分に従って証明書等 授業料免除申請書類 在留カード（写） 宛名ラベル
出願期間 2026 年 7 月 28 日（火）から 2026 年 8 月 3 日（月）（日本時間） 2026 年 8 月 3 日（月）までの消印（日本国内）があるものは受け付けます。海外から出願を検討している人は、2026 年 7 月 17 日（金）までに入試課に申し出。
入学者選抜方法 日本留学試験の成績及び TOEFL のスコア並びに本学が行う小論文・面接の結果を総合して行います。
全課程 2026 年 8 月 25 日（火） 10：00～11：30（90 分）小論文 13：00～ 面接
合格者発表 2026 年 9 月 2 日（水）16 時（予定）
入学手続期間 2026 年 9 月 4 日（金）から 2026 年 9 月 10 日（木）（17 時必着）まで
"""


class KyotoInstituteTech2027UndergradExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_kit_baseline(self) -> None:
        from scripts.kyoto_institute_tech_2027_undergrad_extractor import extract_kit_2027_undergrad_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_kit_2027_undergrad_records(KIT_UNDERGRAD_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "kyoto_institute_tech_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text(self) -> None:
        from scripts.kyoto_institute_tech_2027_undergrad_extractor import extract_kit_2027_undergrad_records
        from scripts.pdf_text_extractor import extract_text_per_page
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        pages = extract_text_per_page(ROOT / "data" / "uploads" / "kyoto_institute_tech_2027_undergrad.pdf")
        text = "\n".join(value for _page, value in sorted(pages.items()))
        records = extract_kit_2027_undergrad_records(text)
        expected = load_json_records(ROOT / "quality_baselines" / "kyoto_institute_tech_2027_undergrad.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 4)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.kyoto_institute_tech_2027_undergrad_extractor import extract_kit_2027_undergrad_records

        self.assertEqual(extract_kit_2027_undergrad_records("京都工芸繊維大学 一般選抜 募集要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "kit.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(KIT_UNDERGRAD_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "kyoto_institute_tech_2027_undergrad_extractor.py"),
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
            self.assertEqual(payload["records"][0]["university"], "京都工芸繊維大学")


if __name__ == "__main__":
    unittest.main()
