from __future__ import annotations

import argparse
import io
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.normalize_fields import (  # noqa: E402
    CRITICAL_EMPTY_HIGHLIGHT_COLUMNS,
    EXCEL_COLUMNS,
    KEY_TO_COLUMN,
    STANDARD_KEY_TO_COLUMN,
    load_and_normalize,
    normalize_extraction_result,
)

CONFIRMED_EXPORT_COLUMNS = [
    ("university", "学校"),
    ("admission_year", "年度"),
    ("admission_period", "入学时期"),
    ("faculty", "学部"),
    ("department", "学科・专攻"),
    ("application_period", "出愿时间"),
    ("deadline_rule", "截止规则"),
    ("eju_session", "EJU 场次"),
    ("eju_japanese", "EJU 日语"),
    ("eju_general", "EJU 综合科目"),
    ("eju_math", "EJU 数学"),
    ("eju_physics", "EJU 物理"),
    ("eju_chemistry", "EJU 化学"),
    ("eju_biology", "EJU 生物"),
    ("english_requirement", "英语要求"),
    ("screening_method", "选考方式"),
    ("screening_schedule", "考试日程"),
    ("result_date", "结果公布"),
    ("enrollment_period", "入学手续"),
    ("eligibility", "出愿资格"),
    ("required_documents", "所需材料"),
    ("evidence", "来源依据"),
    ("prefecture", "地区"),
    ("campus", "校区"),
]


def _load_from_db() -> dict[str, Any]:
    from scripts.db import get_records, init_db

    init_db()
    rows = get_records(limit=10000, offset=0)
    return {"records": rows}


def _normalized_from_args(input_path: Path | None, from_db: bool) -> dict[str, Any]:
    if from_db:
        return normalize_extraction_result(_load_from_db())
    if input_path is None:
        raise ValueError("input JSON is required unless --from-db is used")
    return load_and_normalize(input_path)


def _normalize_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    return normalize_extraction_result({"records": records})


def _column_width(column: str) -> float:
    return {
        "大学名称": 18,
        "入学年度": 12,
        "入学时期": 12,
        "学科/专业": 28,
        "出愿期间": 36,
        "截止规则": 44,
        "EJU场次": 28,
        "EJU日语": 14,
        "EJU综合科目": 18,
        "EJU数学": 24,
        "EJU物理": 14,
        "EJU化学": 14,
        "EJU生物": 14,
        "英语要求": 34,
        "选考方式": 28,
        "选考日程": 34,
        "合格发表日": 30,
        "入学手续期间": 34,
        "都道府县": 12,
        "校区": 28,
        "置信度": 10,
        "是否需要复核": 14,
        "风险等级": 12,
        "警告/备注": 56,
        "大学名": 18,
        "出願時期": 14,
        "学部": 18,
        "学科・専修等": 28,
        "出願期間": 28,
        "必着/消印": 22,
        "EJUの実施回": 24,
        "日本語": 10,
        "記述": 10,
        "総合科目": 12,
        "数学": 16,
        "物理": 10,
        "化学": 10,
        "生物": 10,
        "英語外部資格試験": 34,
        "選考方法": 28,
        "選考日程": 28,
        "合格発表日": 18,
        "入学手続期間": 28,
        "都道府県": 12,
        "キャンパス": 24,
        "信頼度": 10,
        "要確認": 10,
        "リスク": 12,
        "備考": 56,
    }.get(column, 18)


def build_excel_workbook_from_normalized(normalized: dict[str, Any]):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel export") from exc

    records = normalized.get("records") or []
    columns = normalized.get("columns") or EXCEL_COLUMNS
    wb = Workbook()
    ws = wb.active
    if normalized.get("schema") != "standard_jp":
        ws.title = "提取结果"
        ws.append(columns)
        for record in records:
            ws.append([record.get(column, "") for column in columns])
        return wb, len(records)

    ws.title = "抽出結果"
    ws["A1"] = "日本大学留学生入試 募集要項抽出結果"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(columns))
    ws.append([])
    ws.append([])
    ws.append(columns)
    for record in records:
        ws.append([record.get(column, "") for column in columns])

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(name="Microsoft YaHei UI", color="FFFFFF", bold=True)
    title_font = Font(name="Microsoft YaHei UI", color="1F2937", bold=True, size=16)
    thin = Side(style="thin", color="D9E2F3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    warning_fill = PatternFill("solid", fgColor="FFF2CC")

    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28

    for cell in ws[4]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for col_idx, column in enumerate(columns, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = _column_width(column)

    for row in ws.iter_rows(min_row=5, max_row=ws.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            header = columns[cell.column - 1]
            if header in CRITICAL_EMPTY_HIGHLIGHT_COLUMNS and str(cell.value or "").strip() in {"", "要确认", "要確認"}:
                cell.fill = warning_fill
        ws.row_dimensions[row[0].row].height = 48

    ws.freeze_panes = "D5"
    ws.auto_filter.ref = f"A4:{ws.cell(row=ws.max_row, column=len(columns)).coordinate}"
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.oddFooter.center.text = f"生成时间 {datetime.now():%Y-%m-%d %H:%M}"

    readme = wb.create_sheet("README")
    readme["A1"] = "このブックは確認済みまたは抽出済みの募集要項データを標準列に整形したものです。"
    mapping = wb.create_sheet("字段映射")
    mapping.append(["source_key", "column"])
    for key, column in STANDARD_KEY_TO_COLUMN.items():
        mapping.append([key, column])
    return wb, len(records)


def build_excel_workbook(input_path: Path | None = None, *, from_db: bool = False):
    return build_excel_workbook_from_normalized(_normalized_from_args(input_path, from_db))


def build_excel_workbook_from_records(records: list[dict[str, Any]]):
    return build_excel_workbook_from_normalized(_normalize_records(records))


def export_excel_bytes_from_records(records: list[dict[str, Any]]) -> tuple[bytes, int]:
    wb, count = build_excel_workbook_from_records(records)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), count


def export_confirmed_excel_bytes_from_records(records: list[dict[str, Any]]) -> tuple[bytes, int]:
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel export") from exc

    wb = Workbook()
    ws = wb.active
    ws.title = "招生资料"
    ws["A1"] = "已确认招生资料"
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(CONFIRMED_EXPORT_COLUMNS))
    ws.append([])
    ws.append([label for _key, label in CONFIRMED_EXPORT_COLUMNS])
    for record in records:
        ws.append([record.get(key, "") for key, _label in CONFIRMED_EXPORT_COLUMNS])

    header_fill = PatternFill("solid", fgColor="1F2937")
    header_font = Font(name="Microsoft YaHei UI", color="FFFFFF", bold=True)
    title_font = Font(name="Microsoft YaHei UI", color="111827", bold=True, size=16)
    thin = Side(style="thin", color="E5E7EB")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws["A1"].font = title_font
    ws["A1"].alignment = Alignment(horizontal="left", vertical="center")
    ws.row_dimensions[1].height = 28
    for cell in ws[3]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for row in ws.iter_rows(min_row=4, max_row=ws.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
        ws.row_dimensions[row[0].row].height = 42

    for col_idx, (_key, label) in enumerate(CONFIRMED_EXPORT_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = 34 if label in {"出愿时间", "截止规则", "英语要求", "选考方式", "考试日程", "出愿资格", "所需材料", "来源依据"} else 16

    ws.freeze_panes = "E4"
    ws.auto_filter.ref = f"A3:{ws.cell(row=ws.max_row, column=len(CONFIRMED_EXPORT_COLUMNS)).coordinate}"
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), len(records)


def export_excel_bytes(*, from_db: bool = False) -> tuple[bytes, int]:
    wb, count = build_excel_workbook(None, from_db=from_db)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), count


def export_excel(input_path: Path | None, output_path: Path, *, from_db: bool = False) -> dict[str, int | str]:
    wb, count = build_excel_workbook(input_path, from_db=from_db)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(output_path)
    return {"output": str(output_path), "records": count}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export admissions records to the Chinese 25-column master workbook.")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from-db", action="store_true", help="Export confirmed records from the current database.")
    args = parser.parse_args()
    try:
        result = export_excel(args.input, args.output, from_db=args.from_db)
    except Exception as exc:
        print({"error": str(exc)}, file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
