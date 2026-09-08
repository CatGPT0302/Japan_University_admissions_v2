from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from scripts.table_profiles import TableProfile


@dataclass(frozen=True)
class CellBox:
    field: str
    x0: int
    y0: int
    x1: int
    y1: int
    has_symbol: bool = False


@dataclass(frozen=True)
class RowBand:
    row_index: int
    y0: int
    y1: int
    field_cells: dict[str, list[CellBox]] = field(default_factory=dict)


@dataclass(frozen=True)
class TableStructure:
    image_path: Path
    horizontal_lines: list[int]
    vertical_lines: list[int]
    row_bands: list[RowBand]
    profile_name: str = ""

    @property
    def is_usable(self) -> bool:
        return len(self.horizontal_lines) >= 3 and len(self.vertical_lines) >= 3 and bool(self.row_bands)


@dataclass(frozen=True)
class SymbolSummary:
    faculty: str
    eju_fields: dict[str, bool] = field(default_factory=dict)
    english_tests: list[str] = field(default_factory=list)
    department: str = ""


INTERNAL_EJU_FIELDS = {
    "EJU日语": "eju_japanese",
    "EJU综合科目": "eju_general",
    "EJU数学": "eju_math",
    "EJU物理": "eju_physics",
    "EJU化学": "eju_chemistry",
    "EJU生物": "eju_biology",
}
INTERNAL_ENGLISH_FIELD = "english_requirement"
WEAK_MARKERS = ("", "要确认", "要確認", "无明确说明", "需参考官网", "根据学科要求", "不明")
SUMMARY_KEY_SEPARATOR = "||"


def _text(value: Any) -> str:
    return str(value or "").strip()


def _weak(value: Any) -> bool:
    text = _text(value)
    return any(marker == text or (marker and marker in text) for marker in WEAK_MARKERS)


def symbol_summary_key(faculty: str, department: str = "") -> str:
    faculty_text = _text(faculty)
    department_text = _text(department)
    return f"{faculty_text}{SUMMARY_KEY_SEPARATOR}{department_text}" if department_text else faculty_text


def _append_warning(record: dict[str, Any], warning: str) -> None:
    current = _text(record.get("警告/备注") or record.get("warnings") or record.get("warnings_json"))
    if isinstance(record.get("warnings_json"), list):
        values = list(record.get("warnings_json") or [])
        if warning not in values:
            values.append(warning)
        record["warnings_json"] = values
        return
    if warning in current:
        return
    record["警告/备注"] = f"{current}；{warning}" if current else warning


def _get_record_value(record: dict[str, Any], chinese_key: str, internal_key: str) -> Any:
    return record.get(chinese_key, record.get(internal_key, ""))


def _set_record_value(record: dict[str, Any], chinese_key: str, internal_key: str, value: str) -> None:
    if chinese_key in record:
        record[chinese_key] = value
    if internal_key in record or chinese_key not in record:
        record[internal_key] = value


def merge_symbol_summary_into_records(
    records: list[dict[str, Any]],
    summaries: dict[str, SymbolSummary],
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    for record in records:
        next_record = dict(record)
        faculty = _text(next_record.get("学部") or next_record.get("faculty"))
        department = _text(next_record.get("学科/专业") or next_record.get("department"))
        summary = summaries.get(symbol_summary_key(faculty, department)) or summaries.get(faculty)
        if not summary:
            merged.append(next_record)
            continue

        changed = False
        for chinese_key, internal_key in INTERNAL_EJU_FIELDS.items():
            if chinese_key not in summary.eju_fields:
                continue
            current = _get_record_value(next_record, chinese_key, internal_key)
            next_value = "需要" if summary.eju_fields[chinese_key] else "不需要"
            if _text(current) == next_value:
                continue
            _set_record_value(next_record, chinese_key, internal_key, next_value)
            changed = True

        if summary.english_tests:
            current = _get_record_value(next_record, "英语要求", INTERNAL_ENGLISH_FIELD)
            next_value = " / ".join(summary.english_tests)
            if _text(current) != next_value:
                _set_record_value(next_record, "英语要求", INTERNAL_ENGLISH_FIELD, next_value)
                changed = True

        if changed:
            _append_warning(next_record, "Page 5结构增强已覆盖EJU/英语字段，请人工复核")
        merged.append(next_record)
    return merged


def _merge_summary(base: SymbolSummary | None, incoming: SymbolSummary) -> SymbolSummary:
    if base is None:
        return incoming
    eju_fields = dict(base.eju_fields)
    for field, value in incoming.eju_fields.items():
        eju_fields[field] = bool(eju_fields.get(field)) or bool(value)
    english_tests = list(base.english_tests)
    for test in incoming.english_tests:
        if test not in english_tests:
            english_tests.append(test)
    return SymbolSummary(faculty=base.faculty, eju_fields=eju_fields, english_tests=english_tests, department=base.department)


def build_symbol_summaries(structure: TableStructure, profile: TableProfile) -> dict[str, SymbolSummary]:
    rows_by_index = {row.row_index: row for row in structure.row_bands}
    summaries: dict[str, SymbolSummary] = {}
    for mapping in profile.row_mappings:
        row = rows_by_index.get(mapping.row_index)
        if row is None:
            continue
        eju_fields: dict[str, bool] = {}
        for field in profile.eju_column_spans:
            cells = row.field_cells.get(field, [])
            eju_fields[field] = any(cell.has_symbol for cell in cells)
        english_tests = [
            field
            for field in profile.english_column_spans
            if any(cell.has_symbol for cell in row.field_cells.get(field, []))
        ]
        incoming = SymbolSummary(mapping.faculty, eju_fields, english_tests, mapping.department)
        summaries[symbol_summary_key(mapping.faculty, mapping.department)] = incoming
        summaries[mapping.faculty] = _merge_summary(summaries.get(mapping.faculty), incoming)
    return summaries


def _group_centers(points: list[int], max_gap: int = 3) -> list[int]:
    if not points:
        return []
    groups: list[tuple[int, int]] = []
    start = previous = points[0]
    for point in points[1:]:
        if point - previous > max_gap:
            groups.append((start, previous))
            start = point
        previous = point
    groups.append((start, previous))
    return [(start + end) // 2 for start, end in groups]


def _detect_lines(image_path: Path) -> tuple[Any, list[int], list[int]]:
    import cv2
    import numpy as np

    image_bytes = np.frombuffer(image_path.read_bytes(), dtype=np.uint8)
    image = cv2.imdecode(image_bytes, cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError(f"Cannot read image: {image_path}")

    threshold = cv2.adaptiveThreshold(
        image,
        255,
        cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV,
        15,
        10,
    )

    h_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (max(30, image.shape[1] // 60), 1))
    horizontal = cv2.morphologyEx(threshold, cv2.MORPH_OPEN, h_kernel, iterations=1)
    h_projection = (horizontal > 0).sum(axis=1)
    h_points = [int(y) for y in np.where(h_projection > image.shape[1] * 0.18)[0]]

    v_kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (1, max(20, image.shape[0] // 50)))
    vertical = cv2.morphologyEx(threshold, cv2.MORPH_OPEN, v_kernel, iterations=1)
    v_projection = (vertical > 0).sum(axis=0)
    v_points = [int(x) for x in np.where(v_projection > image.shape[0] * 0.08)[0]]

    return threshold, _group_centers(h_points), _group_centers(v_points)


def _cell_has_symbol(threshold: Any, x0: int, y0: int, x1: int, y1: int) -> bool:
    import cv2
    import numpy as np

    pad_x = max(2, (x1 - x0) // 10)
    pad_y = max(2, (y1 - y0) // 8)
    crop = threshold[y0 + pad_y : y1 - pad_y, x0 + pad_x : x1 - pad_x]
    if crop.size == 0:
        return False
    contours, _hierarchy = cv2.findContours(crop, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        area = cv2.contourArea(contour)
        if 4 <= width <= max(24, (x1 - x0) * 0.7) and 4 <= height <= max(24, (y1 - y0) * 0.8) and area >= 6:
            return True
    ink_ratio = float(np.count_nonzero(crop)) / float(crop.size)
    return 0.002 <= ink_ratio <= 0.12


def _build_field_cells(
    threshold: Any,
    y0: int,
    y1: int,
    vertical_lines: list[int],
    profile: TableProfile,
) -> dict[str, list[CellBox]]:
    cells: dict[str, list[CellBox]] = {}
    for field, spans in {**profile.eju_column_spans, **profile.english_column_spans}.items():
        field_cells: list[CellBox] = []
        for start_idx, end_idx in spans:
            if end_idx >= len(vertical_lines):
                continue
            x0 = vertical_lines[start_idx]
            x1 = vertical_lines[end_idx]
            field_cells.append(CellBox(field, x0, y0, x1, y1, _cell_has_symbol(threshold, x0, y0, x1, y1)))
        cells[field] = field_cells
    return cells


def detect_table_structure(image_path: Path, profile: TableProfile) -> TableStructure:
    threshold, horizontal_lines, vertical_lines = _detect_lines(image_path)
    row_bands: list[RowBand] = []
    min_height = 8
    for index, (y0, y1) in enumerate(zip(horizontal_lines, horizontal_lines[1:]), start=1):
        if y1 - y0 < min_height:
            continue
        field_cells = _build_field_cells(threshold, y0, y1, vertical_lines, profile)
        row_bands.append(RowBand(index, y0, y1, field_cells))

    structure = TableStructure(
        image_path=image_path,
        horizontal_lines=horizontal_lines,
        vertical_lines=vertical_lines,
        row_bands=row_bands,
        profile_name=profile.name,
    )
    if os.environ.get("FULL_VISION_DEBUG_TABLE", "").strip() == "1":
        save_debug_overlay(structure)
    return structure


def summarize_table_structure(structure: TableStructure, profile: TableProfile) -> list[str]:
    warnings: list[str] = []
    if len(structure.horizontal_lines) < profile.min_horizontal_lines:
        warnings.append(f"宽表横线检测偏少：{len(structure.horizontal_lines)}")
    if len(structure.vertical_lines) < profile.min_vertical_lines:
        warnings.append(f"宽表竖线检测偏少：{len(structure.vertical_lines)}")
    if len(structure.row_bands) < len(profile.target_faculties):
        warnings.append(f"宽表行带检测偏少：{len(structure.row_bands)}")
    return warnings


def save_debug_overlay(structure: TableStructure) -> Path:
    from PIL import Image, ImageDraw

    image = Image.open(structure.image_path).convert("RGB")
    draw = ImageDraw.Draw(image)
    for y in structure.horizontal_lines:
        draw.line((0, y, image.width, y), fill=(220, 40, 40), width=2)
    for x in structure.vertical_lines:
        draw.line((x, 0, x, image.height), fill=(40, 110, 220), width=2)
    for row in structure.row_bands:
        draw.rectangle((0, row.y0, image.width, row.y1), outline=(40, 160, 80), width=1)
    output = structure.image_path.with_name(structure.image_path.stem + "_table_debug.png")
    image.save(output)
    return output
