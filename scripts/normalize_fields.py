from __future__ import annotations

import argparse
import json
import re
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

STANDARD_COLUMNS = [
    "大学名",
    "出願時期",
    "学部",
    "学科・専修等",
    "出願期間",
    "必着/消印",
    "EJUの実施回",
    "日本語",
    "記述",
    "総合科目",
    "数学",
    "物理",
    "化学",
    "生物",
    "英語外部資格試験",
    "選考方法",
    "選考日程",
    "合格発表日",
    "入学手続期間",
    "都道府県",
    "キャンパス",
    "信頼度",
    "要確認",
    "リスク",
    "備考",
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

STANDARD_KEY_TO_COLUMN = {
    "university": "大学名",
    "admission_year": "出願時期",
    "faculty": "学部",
    "department": "学科・専修等",
    "application_period": "出願期間",
    "deadline_rule": "必着/消印",
    "eju_session": "EJUの実施回",
    "eju_japanese": "日本語",
    "eju_general": "総合科目",
    "eju_math": "数学",
    "eju_physics": "物理",
    "eju_chemistry": "化学",
    "eju_biology": "生物",
    "english_requirement": "英語外部資格試験",
    "screening_method": "選考方法",
    "screening_schedule": "選考日程",
    "result_date": "合格発表日",
    "enrollment_period": "入学手続期間",
    "prefecture": "都道府県",
    "campus": "キャンパス",
    "confidence": "信頼度",
    "needs_review": "要確認",
    "risk_level": "リスク",
    "warnings_json": "備考",
    "warnings": "備考",
}

CRITICAL_EMPTY_HIGHLIGHT_COLUMNS = {
    "出愿期间",
    "EJU场次",
    "英语要求",
    "选考方式",
    "合格发表日",
    "出願期間",
    "必着/消印",
    "EJUの実施回",
    "英語外部資格試験",
    "選考方法",
    "合格発表日",
}


def _text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "是" if value else "否"
    return str(value).strip()


def _warnings(record: dict[str, Any]) -> str:
    raw = record.get("warnings_json", record.get("warnings", ""))
    if isinstance(raw, list):
        return "；".join(_text(item) for item in raw if _text(item))
    if isinstance(raw, dict):
        return json.dumps(raw, ensure_ascii=False)
    return _text(raw)


def _needs_review_cn(value: Any) -> str:
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"是", "yes", "true", "1"}:
            return "是"
        if lowered in {"否", "no", "false", "0"}:
            return "否"
        return value.strip()
    return "是" if bool(value) else "否"


def _split_departments(value: str) -> list[str]:
    text = _text(value)
    if not text:
        return [""]
    if text in {"学部一括", "学科一括"}:
        return [text]
    parts = [part.strip() for part in re.split(r"[、,，]", text) if part.strip()]
    return parts or [text]


def _parse_japanese_dates(value: str) -> list[tuple[int, int, int]]:
    dates: list[tuple[int, int, int]] = []
    current_year: int | None = None
    for match in re.finditer(r"(?:(\d{4})年)?\s*(\d{1,2})月\s*(\d{1,2})日", _text(value)):
        year_raw, month, day = match.groups()
        if year_raw:
            current_year = int(year_raw)
        if current_year is not None:
            dates.append((current_year, int(month), int(day)))
    return dates


def _fmt_date(date: tuple[int, int, int]) -> str:
    year, month, day = date
    return f"{year:04d}/{month:02d}/{day:02d}"


def _application_period(value: str) -> str:
    dates = _parse_japanese_dates(value)
    if len(dates) >= 2:
        return f"{_fmt_date(dates[0])} - {_fmt_date(dates[-1])}"
    if len(dates) == 1:
        return _fmt_date(dates[0])
    return _text(value)


def _deadline_rule(deadline_rule: str, application_period: str) -> str:
    dates = _parse_japanese_dates(deadline_rule) or _parse_japanese_dates(application_period)
    if dates:
        return f"{_fmt_date(dates[-1])} 为止必着"
    return _text(deadline_rule) or "要確認"


def _eju_mark(value: str, *, math: bool = False) -> str:
    text = _text(value)
    if not text:
        return "-"
    if math:
        if re.search(r"コース\s*1|コース1|course\s*1", text, re.I):
            return "〇（コース1）"
        if re.search(r"コース\s*2|コース2|course\s*2", text, re.I):
            return "〇（コース2）"
    return "〇"


def _eju_session(value: str) -> str:
    text = _text(value)
    if not text:
        return "要確認"
    text = text.replace("第一回", "第1回").replace("第１回", "第1回")
    text = text.replace("第二回", "第2回").replace("第２回", "第2回")
    text = text.replace("または", " / ").replace("又は", " / ").replace("、", " / ")

    def repl(match: re.Match[str]) -> str:
        year = match.group(1)
        month = int(match.group(2))
        session = "第1回" if month <= 6 else "第2回"
        return f"{year}年{session}"

    text = re.sub(r"(\d{4})年\s*(\d{1,2})月回", repl, text)
    text = re.sub(r"\s*/\s*", " / ", text)
    return text.strip()


def _english_requirement(value: str) -> str:
    text = _text(value)
    if not text:
        return "要確認"
    cleaned = re.sub(r"日本語", "", text).strip(" /、,，")
    if not cleaned:
        return "要確認"
    pieces: list[str] = []
    patterns = [
        ("TOEFL iBT", r"TOEFL(?:\s*iBT)?(?:\s*[0-9０-９.]+点?以上)?"),
        ("IELTS Academic Module", r"IELTS(?:\s*Academic Module)?(?:\s*[0-9０-９.]+以上)?"),
        ("TOEIC L&R", r"TOEIC(?:\s*L&R)?(?:\s*[0-9０-９.]+点?以上)?"),
    ]
    for label, pattern in patterns:
        match = re.search(pattern, cleaned, re.I)
        if match:
            score = re.search(r"([0-9０-９.]+(?:点)?以上)", match.group(0))
            pieces.append(f"{label} {score.group(1)}" if score else label)
    return " / ".join(pieces) if pieces else cleaned


def _screening_method(value: str) -> str:
    text = _text(value)
    if not text or text == "学力試験":
        return "要確認"
    parts = [part.strip() for part in re.split(r"[、,，/／]+", text) if part.strip()]
    return " / ".join(parts) if parts else text


def _record_to_chinese(record: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = {**defaults, **record}
    row = {column: "" for column in EXCEL_COLUMNS}
    for key, column in KEY_TO_COLUMN.items():
        if column == "警告/备注":
            continue
        value = merged.get(key, "")
        row[column] = _needs_review_cn(value) if column == "是否需要复核" else _text(value)
    row["警告/备注"] = _warnings(merged)
    if not row["入学时期"]:
        row["入学时期"] = "全一回"
    if not row["是否需要复核"]:
        row["是否需要复核"] = "是"
    if not row["风险等级"]:
        row["风险等级"] = "medium"
    return row


def _record_to_standard(record: dict[str, Any], defaults: dict[str, Any]) -> dict[str, Any]:
    merged = {**defaults, **record}
    row = {column: "" for column in STANDARD_COLUMNS}
    row["大学名"] = _text(merged.get("university"))
    row["出願時期"] = _text(merged.get("admission_year"))
    row["学部"] = _text(merged.get("faculty"))
    row["学科・専修等"] = _text(merged.get("department"))
    row["出願期間"] = _application_period(_text(merged.get("application_period")))
    row["必着/消印"] = _deadline_rule(_text(merged.get("deadline_rule")), _text(merged.get("application_period")))
    row["EJUの実施回"] = _eju_session(_text(merged.get("eju_session")))
    row["日本語"] = _eju_mark(_text(merged.get("eju_japanese")))
    row["記述"] = "-"
    row["総合科目"] = _eju_mark(_text(merged.get("eju_general")))
    row["数学"] = _eju_mark(_text(merged.get("eju_math")), math=True)
    row["物理"] = _eju_mark(_text(merged.get("eju_physics")))
    row["化学"] = _eju_mark(_text(merged.get("eju_chemistry")))
    row["生物"] = _eju_mark(_text(merged.get("eju_biology")))
    row["英語外部資格試験"] = _english_requirement(_text(merged.get("english_requirement")))
    row["選考方法"] = _screening_method(_text(merged.get("screening_method")))
    row["選考日程"] = _text(merged.get("screening_schedule"))
    row["合格発表日"] = _application_period(_text(merged.get("result_date")))
    row["入学手続期間"] = _application_period(_text(merged.get("enrollment_period")))
    row["都道府県"] = _text(merged.get("prefecture"))
    row["キャンパス"] = _text(merged.get("campus"))
    row["信頼度"] = _text(merged.get("confidence"))
    row["要確認"] = "はい" if bool(merged.get("needs_review", True)) else "いいえ"
    row["リスク"] = _text(merged.get("risk_level")) or "medium"
    row["備考"] = _warnings(merged)
    return row


def _use_standard_schema(data: dict[str, Any]) -> bool:
    if data.get("schema") == "standard_jp":
        return True
    records = data.get("records") or []
    years = [_text(data.get("admission_year"))] + [_text((record or {}).get("admission_year")) for record in records]
    return any(year.endswith("年度") for year in years if year)


def normalize_extraction_result(data: dict[str, Any]) -> dict[str, Any]:
    defaults = {
        "university": data.get("university", ""),
        "admission_year": data.get("admission_year", ""),
        "admission_period": data.get("admission_period", ""),
    }
    records = data.get("records") or []
    if _use_standard_schema(data):
        normalized_records: list[dict[str, Any]] = []
        for record in records:
            base = dict(record or {})
            for department in _split_departments(_text(base.get("department"))):
                item = dict(base)
                item["department"] = department
                normalized_records.append(_record_to_standard(item, defaults))
        return {"schema": "standard_jp", "columns": STANDARD_COLUMNS, "records": normalized_records}
    return {
        "schema": "chinese_master",
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
    parser = argparse.ArgumentParser(description="Normalize admissions JSON to the selected admissions master schema.")
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
