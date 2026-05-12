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
    load_and_normalize,
    normalize_extraction_result,
)


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
        "学部": 18,
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
    }.get(column, 18)


def build_excel_workbook_from_normalized(normalized: dict[str, Any]):
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        from openpyxl.utils import get_column_letter
    except ImportError as exc:
        raise RuntimeError("openpyxl is required for Excel export") from exc

    records = normalized.get("records") or []
    wb = Workbook()
    ws = wb.active
    ws.title = "提取结果"
    ws.append(EXCEL_COLUMNS)
    for record in records:
        ws.append([record.get(column, "") for column in EXCEL_COLUMNS])

    header_fill = PatternFill("solid", fgColor="1F4E78")
    header_font = Font(name="Microsoft YaHei UI", color="FFFFFF", bold=True)
    thin = Side(style="thin", color="D9E2F3")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    warning_fill = PatternFill("solid", fgColor="FFF2CC")

    for cell in ws[1]:
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = border

    for col_idx, column in enumerate(EXCEL_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = _column_width(column)

    for row in ws.iter_rows(min_row=2, max_row=ws.max_row):
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.border = border
            header = EXCEL_COLUMNS[cell.column - 1]
            if header in CRITICAL_EMPTY_HIGHLIGHT_COLUMNS and str(cell.value or "").strip() in {"", "要确认", "要確認"}:
                cell.fill = warning_fill
        ws.row_dimensions[row[0].row].height = 48

    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    ws.oddFooter.center.text = f"生成时间 {datetime.now():%Y-%m-%d %H:%M}"
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
