from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from openpyxl import load_workbook


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


EXPECTED_COLUMNS = [
    "大学名称",
    "入学年度",
    "入学时期",
    "学部",
    "学科/专业",
    "出愿期间",
    "截止规则",
    "EJU场次",
    "EJU日语",
    "EJU综合科目",
    "EJU数学",
    "EJU物理",
    "EJU化学",
    "EJU生物",
    "英语要求",
    "选考方式",
    "选考日程",
    "合格发表日",
    "入学手续期间",
    "都道府县",
    "校区",
    "置信度",
    "是否需要复核",
    "风险等级",
    "警告/备注",
]


class FullVisionWorkflowTest(unittest.TestCase):
    def test_normalize_records_exports_chinese_25_columns(self) -> None:
        from scripts.normalize_fields import EXCEL_COLUMNS, normalize_extraction_result

        payload = {
            "records": [
                {
                    "university": "早稲田大学",
                    "admission_year": "2027",
                    "admission_period": "全一回",
                    "faculty": "政治経済学部",
                    "department": "政治学科",
                    "application_period": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
                    "deadline_rule": "TAOで必要情報入力、書類アップロード、入学検定料支払いを完了",
                    "eju_session": "2025年11月回または2026年6月回",
                    "eju_japanese": "日本語",
                    "english_requirement": "TOEFL iBT / IELTS Academic Module",
                    "screening_method": "書類選考および筆記試験",
                    "screening_schedule": "9月6日(日)",
                    "result_date": "9月17日(木)",
                    "enrollment_period": "10月20日(火)",
                    "prefecture": "東京都",
                    "campus": "早稲田キャンパス",
                    "confidence": 0.88,
                    "needs_review": True,
                    "risk_level": "medium",
                    "warnings_json": ["理工科以外は安定"],
                }
            ]
        }

        normalized = normalize_extraction_result(payload)

        self.assertEqual(EXCEL_COLUMNS, EXPECTED_COLUMNS)
        self.assertEqual(list(normalized["records"][0].keys()), EXPECTED_COLUMNS)
        self.assertEqual(normalized["records"][0]["大学名称"], "早稲田大学")
        self.assertEqual(normalized["records"][0]["是否需要复核"], "是")
        self.assertEqual(normalized["records"][0]["警告/备注"], "理工科以外は安定")

    def test_export_excel_first_row_is_chinese_master_header(self) -> None:
        from scripts.export_excel import export_excel_bytes_from_records

        content, count = export_excel_bytes_from_records(
            [
                {
                    "university": "早稲田大学",
                    "admission_year": "2027",
                    "faculty": "法学部",
                    "department": "-",
                    "application_period": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
                    "eju_session": "2025年11月回または2026年6月回",
                    "eju_japanese": "日本語",
                    "eju_general": "総合科目",
                    "english_requirement": "TOEFL iBT / IELTS Academic Module",
                    "screening_method": "書類選考 + 面接試験",
                    "confidence": 0.82,
                    "risk_level": "medium",
                }
            ]
        )

        wb = load_workbook(BytesIO(content))
        ws = wb.active

        self.assertEqual(count, 1)
        self.assertEqual(ws.title, "提取结果")
        self.assertEqual([ws.cell(row=1, column=i + 1).value for i in range(25)], EXPECTED_COLUMNS)
        self.assertEqual(ws.cell(row=2, column=1).value, "早稲田大学")
        self.assertEqual(ws.cell(row=2, column=8).value, "2025年11月回または2026年6月回")

    def test_full_vision_parser_accepts_full_document_chinese_json(self) -> None:
        from scripts.full_vision_extractor import (
            evaluate_quality,
            parse_model_response,
            to_internal_records,
        )

        raw = """
        阅读依据摘要：已通读整份PDF，目录页不作为学部。
        {
          "records": [
            {
              "大学名称": "早稲田大学",
              "入学年度": "2027",
              "入学时期": "全一回",
              "学部": "社会科学部",
              "学科/专业": "社会科学科",
              "出愿期间": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
              "截止规则": "出願期間内にTAOで必要情報入力、必要書類アップロード、入学検定料支払いを完了",
              "EJU场次": "2025年11月回または2026年6月回",
              "EJU日语": "日本語",
              "EJU综合科目": "総合科目",
              "EJU数学": "数学コース1 / 数学コース2",
              "EJU物理": "",
              "EJU化学": "",
              "EJU生物": "",
              "英语要求": "TOEFL iBT",
              "选考方式": "書類選考 + 面接試験",
              "选考日程": "二次: 9月18日(金)",
              "合格发表日": "一次: 9月7日(月); 最終: 10月9日(金)",
              "入学手续期间": "第一次: 11月27日(金)",
              "都道府县": "東京都",
              "校区": "早稲田キャンパス",
              "置信度": 0.9,
              "是否需要复核": "是",
              "风险等级": "medium",
              "警告/备注": "数学两列为择一规则，需人工终检。"
            }
          ]
        }
        """

        parsed = parse_model_response(raw)
        internal = to_internal_records(parsed["records"])
        quality = evaluate_quality(parsed["records"])

        self.assertEqual(internal[0]["faculty"], "社会科学部")
        self.assertEqual(internal[0]["eju_session"], "2025年11月回または2026年6月回")
        self.assertEqual(internal[0]["warnings"], ["数学两列为择一规则，需人工终检。"])
        self.assertEqual(quality["quality_status"], "needs_review")
        self.assertIn("可进入人工复核", quality["quality_message"])

    def test_apply_global_fields_backfills_batch_records(self) -> None:
        from scripts.full_vision_extractor import apply_global_fields

        records = [
            {
                "大学名称": "早稲田大学",
                "入学年度": "2027",
                "学部": "文化構想学部",
                "学科/专业": "文化構想学科",
                "EJU场次": "",
            }
        ]
        global_fields = {
            "出愿期间": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
            "EJU场次": "2025年11月回または2026年6月回",
        }

        filled = apply_global_fields(records, global_fields)

        self.assertEqual(filled[0]["出愿期间"], "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）")
        self.assertEqual(filled[0]["EJU场次"], "2025年11月回または2026年6月回")

    def test_parse_page_selection_supports_ranges_and_commas(self) -> None:
        from scripts.full_vision_extractor import _parse_page_selection

        pages = _parse_page_selection("1, 4-6，10 6")

        self.assertEqual(pages, [1, 4, 5, 6, 10])

    def test_page_scheduler_selects_waseda_key_pages_without_toc(self) -> None:
        from scripts.page_scheduler import select_vision_pages

        pdf_path = ROOT / "data" / "uploads" / "waseda_2027_full_vision_test.pdf"
        if not pdf_path.exists():
            self.skipTest("Waseda fixture PDF is not available")

        pages = select_vision_pages(pdf_path, max_pages=8)

        self.assertIsNotNone(pages)
        assert pages is not None
        self.assertIn(5, pages)
        self.assertIn(10, pages)
        self.assertIn(15, pages)
        self.assertNotIn(2, pages)

    def test_waseda_profile_contains_target_faculties(self) -> None:
        from scripts.table_profiles import WASEDA_2027_PROFILE

        self.assertEqual(len(WASEDA_2027_PROFILE.target_faculties), 12)
        self.assertIn("文化構想学部", WASEDA_2027_PROFILE.target_faculties)
        self.assertIn("スポーツ科学部", WASEDA_2027_PROFILE.target_faculties)

    def test_page5_table_structure_detector_finds_grid(self) -> None:
        from scripts.pdf_render import render_pdf_to_images
        from scripts.table_profiles import WASEDA_2027_PROFILE
        from scripts.table_structure_extractor import detect_table_structure

        pdf_path = ROOT / "data" / "uploads" / "waseda_2027_full_vision_test.pdf"
        if not pdf_path.exists():
            self.skipTest("Waseda fixture PDF is not available")

        with tempfile.TemporaryDirectory() as tmp:
            images = render_pdf_to_images(pdf_path, Path(tmp), dpi=120, pages=[5])
            structure = detect_table_structure(images[0], WASEDA_2027_PROFILE)

        self.assertGreaterEqual(len(structure.horizontal_lines), WASEDA_2027_PROFILE.min_horizontal_lines)
        self.assertGreaterEqual(len(structure.vertical_lines), WASEDA_2027_PROFILE.min_vertical_lines)
        self.assertGreaterEqual(len(structure.row_bands), len(WASEDA_2027_PROFILE.target_faculties))
        self.assertTrue(any(cell.has_symbol for row in structure.row_bands for cells in row.field_cells.values() for cell in cells))

    def test_table_symbol_summary_overrides_weak_page5_fields(self) -> None:
        from scripts.table_structure_extractor import SymbolSummary, merge_symbol_summary_into_records

        records = [
            {
                "学部": "社会科学部",
                "学科/专业": "社会科学科",
                "EJU日语": "要确认",
                "EJU综合科目": "要确认",
                "EJU数学": "要确认",
                "EJU物理": "根据学科要求",
                "EJU化学": "根据学科要求",
                "EJU生物": "根据学科要求",
                "英语要求": "无明确说明，需参考官网",
                "警告/备注": "",
            }
        ]
        summaries = {
            "社会科学部": SymbolSummary(
                faculty="社会科学部",
                eju_fields={
                    "EJU日语": True,
                    "EJU综合科目": True,
                    "EJU数学": True,
                    "EJU物理": False,
                    "EJU化学": False,
                    "EJU生物": False,
                },
                english_tests=["TOEFL iBT"],
            )
        }

        merged = merge_symbol_summary_into_records(records, summaries)

        self.assertEqual(merged[0]["EJU日语"], "需要")
        self.assertEqual(merged[0]["EJU综合科目"], "需要")
        self.assertEqual(merged[0]["EJU数学"], "需要")
        self.assertEqual(merged[0]["EJU物理"], "不需要")
        self.assertEqual(merged[0]["EJU化学"], "不需要")
        self.assertEqual(merged[0]["EJU生物"], "不需要")
        self.assertEqual(merged[0]["英语要求"], "TOEFL iBT")
        self.assertIn("Page 5结构增强", merged[0]["警告/备注"])

    def test_structure_enhancement_merges_detected_symbol_summary(self) -> None:
        from scripts.full_vision_extractor import merge_table_structure_enhancement
        from scripts.table_structure_extractor import SymbolSummary, symbol_summary_key

        records = [
            {
                "学部": "文化構想学部",
                "学科/专业": "文化構想学科",
                "EJU日语": "要确认",
                "EJU综合科目": "要确认",
                "EJU数学": "要确认",
                "英语要求": "要确认",
            }
        ]
        summaries = {
            "文化構想学部": SymbolSummary(
                faculty="文化構想学部",
                eju_fields={"EJU日语": True, "EJU综合科目": True, "EJU数学": False},
                english_tests=["TOEFL iBT"],
            ),
            symbol_summary_key("先進理工学部", "化学・生命化学科"): SymbolSummary(
                faculty="先進理工学部",
                department="化学・生命化学科",
                eju_fields={"EJU化学": True, "EJU生物": True},
                english_tests=["TOEFL iBT"],
            )
        }

        merged, warnings = merge_table_structure_enhancement(records, summaries)

        self.assertEqual(merged[0]["EJU日语"], "需要")
        self.assertEqual(merged[0]["EJU数学"], "不需要")
        self.assertEqual(merged[0]["英语要求"], "TOEFL iBT")
        self.assertTrue(any("Page 5结构增强" in warning for warning in warnings))

    def test_structure_enhancement_prefers_department_summary(self) -> None:
        from scripts.full_vision_extractor import merge_table_structure_enhancement
        from scripts.table_structure_extractor import SymbolSummary, symbol_summary_key

        records = [
            {
                "学部": "先進理工学部",
                "学科/专业": "化学・生命化学科",
                "EJU化学": "要确认",
                "EJU生物": "要确认",
            }
        ]
        summaries = {
            "先進理工学部": SymbolSummary(
                faculty="先進理工学部",
                eju_fields={"EJU化学": False, "EJU生物": False},
                english_tests=[],
            ),
            symbol_summary_key("先進理工学部", "化学・生命化学科"): SymbolSummary(
                faculty="先進理工学部",
                department="化学・生命化学科",
                eju_fields={"EJU化学": True, "EJU生物": True},
                english_tests=[],
            ),
        }

        merged, _warnings = merge_table_structure_enhancement(records, summaries)

        self.assertEqual(merged[0]["EJU化学"], "需要")
        self.assertEqual(merged[0]["EJU生物"], "需要")

    def test_structure_enhancement_overrides_confident_model_page5_values(self) -> None:
        from scripts.full_vision_extractor import merge_table_structure_enhancement
        from scripts.table_structure_extractor import SymbolSummary

        records = [
            {
                "学部": "社会科学部",
                "学科/专业": "社会科学科",
                "EJU数学": "不适用",
                "英语要求": "无明确说明，需参考官网",
            }
        ]
        summaries = {
            "社会科学部": SymbolSummary(
                faculty="社会科学部",
                eju_fields={"EJU数学": True},
                english_tests=["TOEFL iBT"],
            )
        }

        merged, _warnings = merge_table_structure_enhancement(records, summaries)

        self.assertEqual(merged[0]["EJU数学"], "需要")
        self.assertEqual(merged[0]["英语要求"], "TOEFL iBT")

    def test_structure_enhancement_adds_missing_profile_records(self) -> None:
        from scripts.full_vision_extractor import merge_table_structure_enhancement
        from scripts.table_structure_extractor import SymbolSummary, symbol_summary_key

        records = [
            {
                "大学名称": "早稲田大学",
                "入学年度": "2027",
                "学部": "社会科学部",
                "学科/专业": "社会科学科",
                "EJU日语": "要确认",
            }
        ]
        summaries = {
            symbol_summary_key("法学部", "法律学科"): SymbolSummary(
                faculty="法学部",
                department="法律学科",
                eju_fields={"EJU日语": True, "EJU综合科目": True},
                english_tests=["TOEFL iBT"],
            )
        }
        global_fields = {
            "大学名称": "早稲田大学",
            "入学年度": "2027",
            "出愿期间": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
            "EJU场次": "2025年11月回または2026年6月回",
        }

        merged, warnings = merge_table_structure_enhancement(records, summaries, global_fields=global_fields)

        law = [record for record in merged if record.get("学部") == "法学部"][0]
        self.assertEqual(law["学科/专业"], "法律学科")
        self.assertEqual(law["EJU日语"], "需要")
        self.assertEqual(law["英语要求"], "TOEFL iBT")
        self.assertEqual(law["EJU场次"], "2025年11月回または2026年6月回")
        self.assertTrue(any("补充" in warning for warning in warnings))

    def test_structure_enhancement_uses_profile_records_as_primary_source(self) -> None:
        from scripts.full_vision_extractor import merge_table_structure_enhancement
        from scripts.table_structure_extractor import SymbolSummary, symbol_summary_key

        records = [
            {
                "大学名称": "早稲田大学",
                "入学年度": "2027",
                "学部": "基幹理工学部",
                "学科/专业": "数理科学科",
                "选考日程": "9月15日(木)",
                "合格发表日": "10月26日(月)",
                "EJU日语": "○",
            },
            {
                "大学名称": "早稲田大学",
                "入学年度": "2027",
                "学部": "基幹理工学部",
                "学科/专业": "学系1",
                "选考日程": "",
                "合格发表日": "",
                "EJU日语": "",
            },
        ]
        summaries = {
            symbol_summary_key("基幹理工学部", "学系1"): SymbolSummary(
                faculty="基幹理工学部",
                department="学系1",
                eju_fields={"EJU日语": True, "EJU数学": True},
                english_tests=[],
            )
        }

        merged, warnings = merge_table_structure_enhancement(records, summaries)

        self.assertEqual(len([record for record in merged if record.get("学部") == "基幹理工学部"]), 1)
        self.assertEqual(merged[0]["学科/专业"], "学系1")
        self.assertEqual(merged[0]["选考日程"], "9月15日(木)")
        self.assertEqual(merged[0]["EJU日语"], "需要")
        self.assertTrue(any("主记录源" in warning for warning in warnings))

    def test_extract_global_eju_session_from_pdf_text(self) -> None:
        from scripts.full_vision_extractor import extract_global_fields_from_pdf_texts

        global_fields = extract_global_fields_from_pdf_texts(
            [
                "学部共通の注意事項",
                "日本留学試験（EJU）は 2025年11月回または2026年6月回 の成績を受理します。",
            ]
        )

        self.assertEqual(global_fields["EJU场次"], "2025年11月回または2026年6月回")

    def test_deterministic_global_fields_override_model_globals(self) -> None:
        from scripts.full_vision_extractor import merge_deterministic_global_fields

        merged = merge_deterministic_global_fields(
            {"EJU场次": "2026年6月", "出愿期间": ""},
            {"EJU场次": "2025年11月回または2026年6月回", "出愿期间": "2026年6月1日(月)10:00～6月18日(木)17:00"},
        )

        self.assertEqual(merged["EJU场次"], "2025年11月回または2026年6月回")
        self.assertEqual(merged["出愿期间"], "2026年6月1日(月)10:00～6月18日(木)17:00")

    def test_symbol_summaries_follow_profile_row_mappings(self) -> None:
        from scripts.pdf_render import render_pdf_to_images
        from scripts.table_profiles import WASEDA_2027_PROFILE
        from scripts.table_structure_extractor import build_symbol_summaries, detect_table_structure

        pdf_path = ROOT / "data" / "uploads" / "waseda_2027_full_vision_test.pdf"
        if not pdf_path.exists():
            self.skipTest("Waseda fixture PDF is not available")

        with tempfile.TemporaryDirectory() as tmp:
            images = render_pdf_to_images(pdf_path, Path(tmp), dpi=120, pages=[5])
            structure = detect_table_structure(images[0], WASEDA_2027_PROFILE)
            summaries = build_symbol_summaries(structure, WASEDA_2027_PROFILE)

        self.assertIn("文化構想学部", summaries)
        self.assertIn("スポーツ科学部", summaries)
        self.assertTrue(summaries["文化構想学部"].eju_fields["EJU日语"])
        self.assertTrue(summaries["スポーツ科学部"].english_tests)

    def test_export_tsv_uses_same_chinese_25_columns(self) -> None:
        payload = {
            "records": [
                {
                    "university": "早稲田大学",
                    "admission_year": "2027",
                    "faculty": "文学部",
                    "department": "文学科",
                    "application_period": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00（日本時間）",
                }
            ]
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

            first_line = output_path.read_text(encoding="utf-8-sig").splitlines()[0]

        self.assertEqual(first_line.split("\t"), EXPECTED_COLUMNS)


if __name__ == "__main__":
    unittest.main()
