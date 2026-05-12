from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


EXCEL_COLUMNS = [
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

KEY_TO_COLUMN = {
    "university": "大学名称",
    "admission_year": "入学年度",
    "admission_period": "入学时期",
    "faculty": "学部",
    "department": "学科/专业",
    "application_period": "出愿期间",
    "deadline_rule": "截止规则",
    "eju_session": "EJU场次",
    "eju_japanese": "EJU日语",
    "eju_general": "EJU综合科目",
    "eju_math": "EJU数学",
    "eju_physics": "EJU物理",
    "eju_chemistry": "EJU化学",
    "eju_biology": "EJU生物",
    "english_requirement": "英语要求",
    "screening_method": "选考方式",
    "screening_schedule": "选考日程",
    "result_date": "合格发表日",
    "enrollment_period": "入学手续期间",
    "prefecture": "都道府县",
    "campus": "校区",
    "confidence": "置信度",
    "needs_review": "是否需要复核",
    "risk_level": "风险等级",
    "warnings_json": "警告/备注",
    "warnings": "警告/备注",
}

CRITICAL_EMPTY_HIGHLIGHT_COLUMNS = {
    "出愿期间",
    "EJU场次",
    "英语要求",
    "选考方式",
    "合格发表日",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value).strip()


def _needs_review(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"是", "yes", "true", "1"}:
            return "是"
        if lowered in {"否", "no", "false", "0"}:
            return "否"
        return value.strip()
    return "是" if bool(value) else "否"


def _warnings(record: dict[str, Any]) -> str:
    raw = record.get("warnings_json", record.get("warnings", ""))
    if isinstance(raw, list):
        return "；".join(_text(item) for item in raw if _text(item))
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return _text(raw)


def _record_to_chinese(record: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = {**defaults, **record}
    row = {column: "" for column in EXCEL_COLUMNS}
    for key, column in KEY_TO_COLUMN.items():
        if key not in merged or column == "警告/备注":
            continue
        value = merged.get(key)
        if column == "是否需要复核":
            row[column] = _needs_review(value)
        else:
            row[column] = _text(value)
    row["警告/备注"] = _warnings(merged)
    if not row["入学时期"]:
        row["入学时期"] = "全一回"
    if not row["是否需要复核"]:
        row["是否需要复核"] = "是"
    if not row["风险等级"]:
        row["风险等级"] = "medium"
    return row


def normalize_extraction_result(data: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "university": data.get("university", ""),
        "admission_year": data.get("admission_year", ""),
        "admission_period": data.get("admission_period", ""),
    }
    records = data.get("records") or []
    return {
        "columns": EXCEL_COLUMNS,
        "records": [_record_to_chinese(dict(record or {}), defaults) for record in records],
    }


def load_and_normalize(input_path: Path) -> dict[str, Any]:
    data = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        data = {"records": data}
    if not isinstance(data, dict):
        raise ValueError("input JSON must be an object or a list of records")
    return normalize_extraction_result(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize admissions JSON to the Chinese 25-column master schema.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    normalized = load_and_normalize(args.input)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")
    print({"output": str(args.output), "records": len(normalized.get("records") or [])})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
