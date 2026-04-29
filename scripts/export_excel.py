from __future__ import annotations

import argparse
import io
import json
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
    load_and_normalize,
    normalize_extraction_result,
)


TITLE = "日本大学留学生入試 募集要項抽出結果"
HEADER_FILL = "334155"
HEADER_FONT = "FFFFFF"
CRITICAL_FILL = "FFF2CC"
BORDER_COLOR = "CBD5E1"


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


def _column_widths() -> dict[str, float]:
    return {
        "大学名": 18,
        "出願時期": 12,
        "学部": 18,
        "学科・専修等": 28,
        "出願期間": 24,
        "必着/消印": 34,
        "出願要件・基準点など": 42,
        "EJUの実施回": 16,
        "日本語": 14,
        "総合科目": 14,
        "数学": 18,
        "物理": 12,
        "化学": 12,
        "生物": 12,
        "英語外部資格試験": 32,
        "選考方法": 24,
        "選考日程": 24,
        "合格発表日": 16,
        "入学手続期間": 24,
        "都道府県": 12,
        "キャンパス": 18,
        "更新人/更新日期": 18,
    }


def _style_results_sheet(ws, records: list[dict[str, Any]]) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    ws.title = "抽出結果"
    ws["A1"] = TITLE
    ws["A1"].font = Font(name="Meiryo", size=14, bold=True)
    ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=len(EXCEL_COLUMNS))
    generated = datetime.now().strftime("%Y/%m/%d %H:%M")
    ws["A2"] = f"生成時間: {generated} / AI抽取初稿。最終判断は大学公式募集要項を確認してください。"
    ws.merge_cells(start_row=2, start_column=1, end_row=2, end_column=len(EXCEL_COLUMNS))

    header_fill = PatternFill(fill_type="solid", fgColor=HEADER_FILL)
    header_font = Font(name="Meiryo", size=10, bold=True, color=HEADER_FONT)
    body_font = Font(name="Meiryo", size=10)
    thin = Side(style="thin", color=BORDER_COLOR)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    yellow = PatternFill(fill_type="solid", fgColor=CRITICAL_FILL)

    for col_idx, column in enumerate(EXCEL_COLUMNS, start=1):
        cell = ws.cell(row=4, column=col_idx, value=column)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border
        ws.column_dimensions[get_column_letter(col_idx)].width = _column_widths().get(column, 16)

    for row_idx, record in enumerate(records, start=5):
        for col_idx, column in enumerate(EXCEL_COLUMNS, start=1):
            value = record.get(column, "")
            cell = ws.cell(row=row_idx, column=col_idx, value=value)
            cell.font = body_font
            cell.border = border
            cell.alignment = Alignment(vertical="center", wrap_text=True)
            if column in CRITICAL_EMPTY_HIGHLIGHT_COLUMNS and str(value or "").strip() in {"", "要確認"}:
                cell.fill = yellow

    ws.freeze_panes = "D5"
    last_row = max(5, 4 + len(records))
    ws.auto_filter.ref = f"A4:{get_column_letter(len(EXCEL_COLUMNS))}{last_row}"
    ws.row_dimensions[1].height = 24
    ws.row_dimensions[2].height = 36
    ws.row_dimensions[4].height = 28


def _build_readme_sheet(wb) -> None:
    from openpyxl.styles import Alignment, Font

    ws = wb.create_sheet("README")
    ws["A1"] = "README"
    ws["A1"].font = Font(name="Meiryo", size=14, bold=True)
    lines = [
        "本表由 AI 辅助抽取生成。",
        "空欄或「要確認」表示原文未明确或需要人工复核。",
        "黄色字段为重点确认项目。",
        "最终出愿判断必须以大学官方募集要項为准。",
        "AI抽取结果应进入 staging，并经过人工确认后再作为正式数据使用。",
    ]
    for idx, line in enumerate(lines, start=3):
        ws.cell(row=idx, column=1, value=line)
        ws.cell(row=idx, column=1).font = Font(name="Meiryo", size=11)
        ws.cell(row=idx, column=1).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 92


def _build_mapping_sheet(wb) -> None:
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

    ws = wb.create_sheet("字段映射")
    headers = ["JSON key", "Excel column"]
    fill = PatternFill(fill_type="solid", fgColor=HEADER_FILL)
    font = Font(name="Meiryo", bold=True, color=HEADER_FONT)
    side = Side(style="thin", color=BORDER_COLOR)
    border = Border(left=side, right=side, top=side, bottom=side)
    for col_idx, header in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=header)
        cell.fill = fill
        cell.font = font
        cell.border = border
        cell.alignment = Alignment(horizontal="center")
    for row_idx, (key, column) in enumerate(KEY_TO_COLUMN.items(), start=2):
        ws.cell(row=row_idx, column=1, value=key).border = border
        ws.cell(row=row_idx, column=2, value=column).border = border
    ws.column_dimensions["A"].width = 28
    ws.column_dimensions["B"].width = 28


def build_excel_workbook_from_normalized(normalized: dict[str, Any]):
    try:
        from openpyxl import Workbook
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel export") from exc

    records = normalized.get("records") or []
    wb = Workbook()
    ws = wb.active
    _style_results_sheet(ws, records)
    _build_readme_sheet(wb)
    _build_mapping_sheet(wb)
    return wb, len(records)


def build_excel_workbook(input_path: Path | None = None, *, from_db: bool = False):
    normalized = _normalized_from_args(input_path, from_db)
    return build_excel_workbook_from_normalized(normalized)


def build_excel_workbook_from_records(records: list[dict[str, Any]]):
    normalized = _normalize_records(records)
    return build_excel_workbook_from_normalized(normalized)


def export_excel_bytes_from_records(records: list[dict[str, Any]]) -> tuple[bytes, int]:
    wb, count = build_excel_workbook_from_records(records)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue(), count


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
    parser = argparse.ArgumentParser(description="Export normalized admissions records to the polished Excel master table.")
    parser.add_argument("input", type=Path, nargs="?")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--from-db", action="store_true", help="Export confirmed records from the current database.")
    args = parser.parse_args()
    try:
        result = export_excel(args.input, args.output, from_db=args.from_db)
    except Exception as exc:
        print(json.dumps({"error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
