from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


MEIJI_TEXT = """
明治大学 2027年度外国人留学生入学試験 試験科目・日程等一覧（学部）
法学部 法律学科 Ⅰ ２０名
①日本語
②総合科目、数学(コース１または２）のうち、いずれか１科目
合計２科目
TOEFL iBT ２０２６年１月２０日以前受験 ４５以上
小論文 口頭試問
２０２６年 １２月１１日（金）
商学部 商学科 Ⅰ ３０名
①日本語
②総合科目
合計２科目
TOEFL iBT ２０２６年１月２０日以前受験 ４８以上
TOEIC L&R ６００以上
書類選考 ２０２６年 １０月２３日（金）
２０２６年 １２月５日（土）
２０２６年 １２月１１日（金）
口頭試問（オンライン）
政治経済学部 政治学科 経済学科 政策学科 Ⅰ
①日本語
②総合科目、数学(コース１）のうち、いずれか１科目
合計２科目
TOEFL iBT TOEIC L&R IELTS 出願基準点なし
書類選考 ２０２６年１１月６日（金）
２０２６年１２月５日（土）
小論文 口頭試問
２０２６年１２月１１日（金）
文学部 文学科 史学地理学科 心理社会学科 Ⅰ
①日本語
②総合科目
③数学(コース１)
合計３科目
書類選考 ２０２６年１０月２１日（水）
２０２６年１１月２８日（土）
口頭試問
２０２６年１２月２日（水）
情報ｺﾐｭﾆｹｰｼｮﾝ学部 情報ｺﾐｭﾆｹｰｼｮﾝ学科
小論文 面接 １２月１５日（火） Ⅰ ２０名
①日本語
②総合科目
合計２科目
TOEFL iBT ２０２６年１月２０日以前受験 ４２以上
TOEIC L&R ５５０以上
理工学部 電気電子生命学科 機械工学科 機械情報工学科 建築学科 応用化学学科 情報科学科 数学科 物理学科 Ⅰ ２０名
①日本語
②③理科(物理・化学）
④数学(コース２）
合計４科目
TOEFL iBT TOEIC L&R 出願基準点なし
小論文 口頭試問
経営学部 経営学科 会計学科 公共経営学科 Ⅰ ４０名
①日本語
②総合科目
合計２科目
TOEFL iBT TOEIC L&R IELTS 出願基準点なし
書類選考 口頭試問
国際日本学部 国際日本学科 Ⅰ ４０名
①日本語
②総合科目
合計２科目
TOEFL iBT ２０２６年１月２０日以前受験 ４４以上
TOEIC L&R ５６５以上
IELTS ４．０以上
２０２６年１１月２４日（火）
２０２６年１２月１９日（土）
１０：００～
口頭試問
２０２６年１２月２４日（木）
国際日本学部 （国外在住者） 国際日本学科 Ⅱ
①日本語
②総合科目
合計２科目
TOEFL iBT TOEIC L&R ６００以上 IELTS ４．０以上
２０２６年１２月２４日（木）
商学部（国外在住者） 商学科 Ⅱ
３０名（Ⅰ型含む）
２０２６年１０月２０日（火）～１０月２７日（火）
①日本語
②総合科目
③数学（コース１）
合計３科目
２０２５年度第１回
２０２５年度第２回
２０２６年度第１回
２０２６年度第２回
TOEFL iBT ２０２６年１月２０日以前受験 ４８以上
TOEIC L&R ６００以上
２０２４年１２月１日（日）～２０２６年９月３０日（水）
書類選考のみ
２０２７年１月１４日（木）
"""


class MeijiScheduleExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_meiji_baseline(self) -> None:
        from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        records = extract_meiji_2027_schedule_records(MEIJI_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "meiji_2027_schedule.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 10)
        self.assertIn("eju_japanese", records[0])
        self.assertIn("eju_general", records[0])
        self.assertIn("eju_math", records[0])
        self.assertTrue(report["passed"], report)

    def test_extracts_seed_records_from_real_pdf_text_fixture(self) -> None:
        from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records
        from scripts.quality_baseline import evaluate_against_expected, load_json_records

        fixture_text = (ROOT / "tests" / "fixtures" / "meiji_2027_schedule_text.txt").read_text(encoding="utf-8")
        records = extract_meiji_2027_schedule_records(fixture_text)
        expected = load_json_records(ROOT / "quality_baselines" / "meiji_2027_schedule.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 10)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records

        self.assertEqual(extract_meiji_2027_schedule_records("早稲田大学 入試要項"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "meiji.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(MEIJI_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "meiji_schedule_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["records"]), 10)
            self.assertEqual(payload["records"][0]["university"], "明治大学")

    def test_text_path_uses_meiji_seed_without_llm_call(self) -> None:
        from scripts.extract_direct import _run_text_path

        university = self._seed_university()
        with (
            patch("scripts.extract_direct._read_pdf_text", return_value=(MEIJI_TEXT, {1: MEIJI_TEXT})),
            patch("scripts.extract_direct._insert_result", return_value=10) as insert_result,
            patch("scripts.extract_direct._call_openai", side_effect=AssertionError("LLM should not be called")),
        ):
            result = _run_text_path(1, Path("dummy.pdf"), university, "2027")

        self.assertEqual(result["mode"], "deterministic_text")
        self.assertEqual(result["records"], 10)
        self.assertEqual(result["inserted"], 10)
        insert_result.assert_called_once()

    def _seed_university(self) -> str:
        from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records

        return extract_meiji_2027_schedule_records(MEIJI_TEXT)[0]["university"]


if __name__ == "__main__":
    unittest.main()
