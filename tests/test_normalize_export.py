from __future__ import annotations

import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


class NormalizeExportTest(unittest.TestCase):
    def test_normalize_records_expand_departments_and_eju_display(self) -> None:
        from scripts.normalize_fields import normalize_extraction_result

        data = {
            "university": "早稲田大学",
            "admission_year": "2027年度",
            "records": [
                {
                    "faculty": "政治経済学部",
                    "department": "政治学科、経済学科、国際政治経済学科",
                    "application_period": "2026年6月1日（月）10:00 ～ 6月18日（木）17:00",
                    "deadline_rule": "TAO完了。TOEFL直送書類は出願期限までに到着",
                    "eju_japanese": "日本語",
                    "eju_math": "数学(コース1)",
                    "eju_physics": "",
                    "eju_chemistry": "",
                    "eju_biology": "",
                    "english_requirement": "TOEFL / IELTS",
                    "screening_method": "書類選考 / 面接",
                },
                {
                    "faculty": "法学部",
                    "department": "学部一括",
                    "eju_general": "総合科目",
                    "english_requirement": "日本語 TOEFL",
                },
            ],
        }

        normalized = normalize_extraction_result(data)
        records = normalized["records"]

        self.assertEqual([r["学科・専修等"] for r in records[:3]], ["政治学科", "経済学科", "国際政治経済学科"])
        self.assertEqual(records[3]["学科・専修等"], "学部一括")
        self.assertEqual(records[0]["日本語"], "〇")
        self.assertEqual(records[0]["数学"], "〇（コース1）")
        self.assertEqual(records[0]["物理"], "-")
        self.assertEqual(records[0]["出願期間"], "2026/06/01 - 2026/06/18")
        self.assertEqual(records[3]["総合科目"], "〇")
        self.assertEqual(records[0]["英語外部資格試験"], "TOEFL iBT / IELTS Academic Module")
        self.assertNotIn("日本語", records[3]["英語外部資格試験"])
        self.assertIn("外部試験スコア", records[0]["必着/消印"])

    def test_export_tsv_uses_fixed_columns(self) -> None:
        payload = {
            "university": "サンプル大学",
            "admission_year": "2027年度",
            "records": [
                {
                    "faculty": "商学部",
                    "department": "学部一括",
                    "eju_general": "総合科目",
                    "english_requirement": "",
                    "screening_method": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            output_path = tmp_path / "out.tsv"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "export_tsv.py"), str(input_path), "--output", str(output_path)],
                check=True,
                cwd=ROOT,
            )

            with output_path.open("r", encoding="utf-8-sig", newline="") as fh:
                rows = list(csv.reader(fh, delimiter="\t"))

        self.assertEqual(rows[0][:6], ["大学名", "出願時期", "学部", "学科・専修等", "出願期間", "必着/消印"])
        self.assertEqual(rows[1][0:4], ["サンプル大学", "2027年度", "商学部", "学部一括"])
        self.assertEqual(rows[1][9], "〇")
        self.assertEqual(rows[1][10], "-")
        self.assertEqual(rows[1][14], "要確認")

    def test_export_excel_creates_polished_workbook(self) -> None:
        from openpyxl import load_workbook

        payload = {
            "university": "サンプル大学",
            "admission_year": "2027年度",
            "records": [
                {
                    "faculty": "商学部",
                    "department": "学部一括",
                    "eju_general": "総合科目",
                    "english_requirement": "",
                    "screening_method": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            output_path = tmp_path / "out.xlsx"
            input_path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

            subprocess.run(
                [sys.executable, str(ROOT / "scripts" / "export_excel.py"), str(input_path), "--output", str(output_path)],
                check=True,
                cwd=ROOT,
            )

            wb = load_workbook(output_path)
            self.assertEqual(wb.sheetnames, ["抽出結果", "README", "字段映射"])
            ws = wb["抽出結果"]
            self.assertEqual(ws["A1"].value, "日本大学留学生入試 募集要項抽出結果")
            self.assertEqual(ws.freeze_panes, "D5")
            self.assertEqual([ws.cell(row=4, column=i + 1).value for i in range(6)], ["大学名", "出願時期", "学部", "学科・専修等", "出願期間", "必着/消印"])
            self.assertEqual(ws.cell(row=5, column=1).value, "サンプル大学")
            self.assertEqual(ws.cell(row=5, column=15).value, "要確認")
            self.assertEqual(ws.cell(row=5, column=15).fill.fgColor.rgb, "00FFF2CC")

    def test_export_excel_bytes_from_records_uses_standard_workbook(self) -> None:
        from io import BytesIO

        from openpyxl import load_workbook

        from scripts.export_excel import export_excel_bytes_from_records

        content, count = export_excel_bytes_from_records(
            [
                {
                    "university": "明治大学",
                    "admission_year": "2026年度",
                    "faculty": "理工学部",
                    "department": "機械工学科、電気電子生命学科",
                    "eju_session": "第一回 / 第二回",
                    "eju_japanese": "日本語",
                    "eju_math": "数学コース2",
                    "eju_physics": "物理・化学・生物から2科目",
                    "eju_chemistry": "物理・化学・生物から2科目",
                    "eju_biology": "物理・化学・生物から2科目",
                    "english_requirement": "TOEFL / IELTS / TOEIC",
                    "screening_method": "書類選考 / 面接",
                }
            ]
        )

        self.assertGreater(len(content), 1000)
        self.assertEqual(count, 2)
        wb = load_workbook(BytesIO(content))
        self.assertEqual(wb.sheetnames, ["抽出結果", "README", "字段映射"])
        ws = wb["抽出結果"]
        self.assertEqual(ws["A1"].value, "日本大学留学生入試 募集要項抽出結果")
        self.assertEqual(ws.freeze_panes, "D5")
        self.assertEqual(ws.cell(row=4, column=1).value, "大学名")
        self.assertEqual(ws.cell(row=5, column=1).value, "明治大学")
        self.assertEqual(ws.cell(row=5, column=4).value, "機械工学科")
        self.assertEqual(ws.cell(row=6, column=4).value, "電気電子生命学科")
        self.assertEqual(ws.cell(row=5, column=11).value, "〇（コース2）")
        self.assertEqual(ws.cell(row=5, column=15).value, "TOEFL iBT / IELTS Academic Module / TOEIC L&R")


if __name__ == "__main__":
    unittest.main()
