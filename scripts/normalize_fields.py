from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any


EXCEL_COLUMNS = [
    "大学名",
    "出願時期",
    "学部",
    "学科・専修等",
    "出願期間",
    "必着/消印",
    "出願要件・基準点など",
    "EJUの実施回",
    "日本語",
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
    "更新人/更新日期",
]

KEY_TO_COLUMN = {
    "university": "大学名",
    "admission_period": "出願時期",
    "admission_year": "出願時期",
    "faculty": "学部",
    "department": "学科・専修等",
    "application_period": "出願期間",
    "deadline_rule": "必着/消印",
    "requirements_note": "出願要件・基準点など",
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
    "updated_by_date": "更新人/更新日期",
}

EJU_FIELDS = [
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
]

PROTECTED_DEPARTMENT_VALUES = {"学部一括", "学科一括", "学系一括", "若干名", "未定", "要確認"}
ENGLISH_TOKENS = ("TOEFL", "IELTS", "TOEIC", "英検", "ドイツ語", "フランス語")
EJU_TOKENS = ("日本語", "総合科目", "数学", "物理", "化学", "生物", "EJU", "日本留学試験")
CRITICAL_EMPTY_HIGHLIGHT_COLUMNS = {"出願期間", "必着/消印", "EJUの実施回", "英語外部資格試験", "選考方法", "合格発表日"}


def _s(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _append_note(record: dict[str, Any], note: str) -> None:
    note = _s(note)
    if not note:
        return
    notes = list(record.get("_normalized_notes") or [])
    if note not in notes:
        notes.append(note)
    record["_normalized_notes"] = notes


def _append_warning(record: dict[str, Any], warning: str) -> None:
    warning = _s(warning)
    if not warning:
        return
    warnings = list(record.get("warnings") or record.get("warnings_json") or [])
    if warning not in warnings:
        warnings.append(warning)
    record["warnings"] = warnings
    record["warnings_json"] = warnings


def _date_token(year: str, month: str, day: str) -> str:
    return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"


def _normalize_date_text(value: Any) -> str:
    text = _s(value)
    if not text:
        return ""
    text = text.translate(str.maketrans("０１２３４５６７８９", "0123456789"))
    text = re.sub(r"[（(][月火水木金土日][）)]", "", text)
    text = re.sub(r"\s+", "", text)

    first = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", text)
    if first:
        year = first.group(1)
        rest = text[first.end():]
        second = re.search(r"(\d{1,2})月(\d{1,2})日", rest)
        if second:
            return f"{_date_token(year, first.group(2), first.group(3))} - {_date_token(year, second.group(1), second.group(2))}"
        return _date_token(year, first.group(2), first.group(3))

    explicit = re.findall(r"(20\d{2})[年/.-](\d{1,2})[月/.-](\d{1,2})日?", text)
    if explicit:
        tokens = [_date_token(y, m, d) for y, m, d in explicit]
        if len(tokens) >= 2:
            sep = " - " if any(ch in text for ch in ("～", "〜", "-")) else " / "
            return sep.join(tokens)
        return tokens[0]

    compact = re.findall(r"(20\d{2})/(\d{1,2})/(\d{1,2})", text)
    if compact:
        tokens = [_date_token(y, m, d) for y, m, d in compact]
        return " - ".join(tokens) if len(tokens) == 2 else " / ".join(tokens)
    return _s(value)


def normalize_dates(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    for field in ("application_period", "screening_schedule", "result_date", "enrollment_period"):
        if field in r:
            r[field] = _normalize_date_text(r.get(field))
    return r


def normalize_deadline_rule(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    source = " ".join(
        _s(r.get(field))
        for field in ("deadline_rule", "application_period", "requirements_note")
        if _s(r.get(field))
    )
    labels: list[str] = []
    if "必着" in source or "到着" in source:
        labels.append("出願期限までに必着")
    if "消印有効" in source:
        labels.append("消印有効")
    if "TAO" in source:
        labels.append("TAO期間内完了")
    if "UCARO" in source or "オンライン" in source or "アップロード" in source:
        labels.append("オンライン出願期間内完了")
    if any(token in source for token in ("TOEFL", "IELTS", "TOEIC", "直送")):
        labels.append("外部試験スコアは出願期限までに直送・到着必須")
    if "支払" in source or "支払い" in source or "入学検定料" in source:
        labels.append("入学検定料支払い期限内完了")
    r["deadline_rule"] = " / ".join(dict.fromkeys(labels)) if labels else _s(r.get("deadline_rule"))
    return r


def _normalize_eju_session(value: Any) -> str:
    text = _s(value).translate(str.maketrans("１２", "12"))
    if not text:
        return "要確認"
    rounds: list[str] = []
    if re.search(r"第\s*1\s*回|第一回|6月|7月", text):
        rounds.append("第一回")
    if re.search(r"第\s*2\s*回|第二回|11月", text):
        rounds.append("第二回")
    return " / ".join(dict.fromkeys(rounds)) if rounds else text


def _eju_base_display(value: Any, label: str) -> str:
    text = _s(value)
    if not text:
        return ""
    if any(token in text for token in ENGLISH_TOKENS):
        return ""
    if "不要" in text or text in {"-", "なし", "無し", "不問"}:
        return "-"
    score = re.search(rf"({re.escape(label)}\s*\d{{2,3}}\s*点以上)", text)
    if score:
        return re.sub(r"\s+", "", score.group(1))
    if "△" in text or "選択" in text or "いずれか" in text or "から" in text:
        return "△"
    if "○" in text or "〇" in text or label in text or "必須" in text or "必要" in text:
        return "〇"
    if "要確認" in text:
        return "要確認"
    return text


def _normalize_math_display(value: Any) -> str:
    text = _s(value)
    if not text:
        return ""
    if any(token in text for token in ENGLISH_TOKENS):
        return ""
    score = re.search(r"数学\s*(\d{2,3})\s*点以上", text)
    suffix = ""
    if re.search(r"コース\s*1.*コース\s*2|コース\s*1\s*または\s*2|コース1または2", text):
        suffix = "（コース1または2）"
    elif re.search(r"コース\s*1|コース1", text):
        suffix = "（コース1）"
    elif re.search(r"コース\s*2|コース2", text):
        suffix = "（コース2）"
    if score:
        return f"数学{score.group(1)}点以上{suffix}"
    if "不要" in text or text in {"-", "なし", "無し", "不問"}:
        return "-"
    if "△" in text or "選択" in text or "いずれか" in text:
        return "△"
    if "数学" in text or "○" in text or "〇" in text or "必須" in text or "必要" in text:
        return f"〇{suffix}" if suffix else "〇"
    if "要確認" in text:
        return "要確認"
    return text


def _science_choice_note(record: dict[str, Any]) -> str:
    source = " ".join(_s(record.get(field)) for field in EJU_FIELDS + ["requirements_note"] if _s(record.get(field)))
    match = re.search(r"物理[・、,]化学[・、,]生物.{0,12}?([12１２])\s*科目", source)
    if not match:
        match = re.search(r"理科.{0,16}?([12１２])\s*科目", source)
    if not match:
        return ""
    count = match.group(1).translate(str.maketrans("１２", "12"))
    return f"理科は物理・化学・生物から{count}科目選択"


def normalize_eju_display(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    choice_note = _science_choice_note(r)
    if choice_note:
        _append_note(r, choice_note)
        for field in ("eju_physics", "eju_chemistry", "eju_biology"):
            r[field] = "△"

    raw_any = any(_s(r.get(field)) for field in EJU_FIELDS)
    r["eju_session"] = _normalize_eju_session(r.get("eju_session"))
    r["eju_japanese"] = _eju_base_display(r.get("eju_japanese"), "日本語")
    r["eju_general"] = _eju_base_display(r.get("eju_general"), "総合科目")
    r["eju_math"] = _normalize_math_display(r.get("eju_math"))
    r["eju_physics"] = _eju_base_display(r.get("eju_physics"), "物理")
    r["eju_chemistry"] = _eju_base_display(r.get("eju_chemistry"), "化学")
    r["eju_biology"] = _eju_base_display(r.get("eju_biology"), "生物")

    for field in EJU_FIELDS:
        if not _s(r.get(field)):
            r[field] = "-" if raw_any else "要確認"
    return r


def _extract_english_labels(value: Any) -> list[str]:
    text = _s(value)
    labels: list[str] = []
    if re.search(r"TOEFL", text, re.IGNORECASE):
        labels.append("TOEFL iBT")
    if re.search(r"IELTS", text, re.IGNORECASE):
        labels.append("IELTS Academic Module")
    if re.search(r"TOEIC", text, re.IGNORECASE):
        labels.append("TOEIC L&R")
    if "英検" in text:
        labels.append("英検")
    if "ドイツ語" in text:
        labels.append("ドイツ語")
    if "フランス語" in text:
        labels.append("フランス語")
    return list(dict.fromkeys(labels))


def normalize_english_requirement(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    source = _s(r.get("english_requirement"))
    contaminated = any(token in source for token in EJU_TOKENS)
    labels = _extract_english_labels(source)
    if labels:
        r["english_requirement"] = " / ".join(labels)
        if contaminated:
            _append_warning(r, "英語外部資格試験 contained EJU text and was conservatively normalized")
    elif any(token in source for token in ("不要", "なし", "無し", "不問")):
        r["english_requirement"] = "-"
    elif source in {"-", "任意"}:
        r["english_requirement"] = source
    else:
        r["english_requirement"] = "要確認"
        if contaminated:
            _append_warning(r, "英語外部資格試験 cleared because it contained EJU subject content")
    return r


def _split_departments(value: str) -> list[str]:
    text = _s(value)
    if not text:
        return ["要確認"]
    if text in PROTECTED_DEPARTMENT_VALUES:
        return [text]
    if "一括" in text or text in {"若干名", "未定"}:
        return [text]
    parts = [part.strip() for part in re.split(r"[、,，／/]+", text) if part.strip()]
    return parts or [text]


def _looks_invented_department(faculty: str, department: str) -> bool:
    faculty = _s(faculty)
    department = _s(department)
    return bool(faculty.endswith("学部") and department == faculty[:-2] + "学科")


def expand_department_rows(record: dict[str, Any]) -> list[dict[str, Any]]:
    base = deepcopy(record)
    faculty = _s(base.get("faculty"))
    department = _s(base.get("department"))
    if _looks_invented_department(faculty, department):
        base["department"] = "要確認"
        _append_warning(base, "department looked invented from faculty name; verify original 募集単位")
        return [base]
    rows: list[dict[str, Any]] = []
    for department_part in _split_departments(department):
        item = deepcopy(base)
        item["department"] = department_part
        rows.append(item)
    return rows


def _requirements_note(record: dict[str, Any]) -> str:
    values: list[str] = []
    for key in ("requirements_note", "admission_requirements", "notes"):
        value = record.get(key)
        if isinstance(value, list):
            values.extend(_s(item) for item in value if _s(item))
        elif _s(value):
            values.append(_s(value))
    for item in record.get("_normalized_notes") or []:
        if _s(item):
            values.append(_s(item))
    for warning in record.get("warnings") or record.get("warnings_json") or []:
        warning = _s(warning)
        if warning and any(token in warning for token in ("△", "※", "注", "選択", "要確認", "条件", "点以上")):
            values.append(warning)
    return " / ".join(dict.fromkeys(values))


def normalize_record(record: dict[str, Any], top_level: dict[str, Any] | None = None) -> dict[str, Any]:
    top = top_level or {}
    r = dict(record)
    r = normalize_dates(r)
    r = normalize_deadline_rule(r)
    r = normalize_eju_display(r)
    r = normalize_english_requirement(r)

    output = {column: "" for column in EXCEL_COLUMNS}
    output["大学名"] = _s(r.get("university")) or _s(top.get("university"))
    output["出願時期"] = _s(r.get("admission_period")) or _s(r.get("admission_year")) or _s(top.get("admission_year"))
    output["学部"] = _s(r.get("faculty"))
    output["学科・専修等"] = _s(r.get("department")) or "要確認"
    output["出願期間"] = _s(r.get("application_period"))
    output["必着/消印"] = _s(r.get("deadline_rule"))
    output["出願要件・基準点など"] = _requirements_note(r)
    output["EJUの実施回"] = _s(r.get("eju_session"))
    output["日本語"] = _s(r.get("eju_japanese"))
    output["総合科目"] = _s(r.get("eju_general"))
    output["数学"] = _s(r.get("eju_math"))
    output["物理"] = _s(r.get("eju_physics"))
    output["化学"] = _s(r.get("eju_chemistry"))
    output["生物"] = _s(r.get("eju_biology"))
    output["英語外部資格試験"] = _s(r.get("english_requirement"))
    output["選考方法"] = _s(r.get("screening_method")) or "要確認"
    output["選考日程"] = _s(r.get("screening_schedule"))
    output["合格発表日"] = _s(r.get("result_date"))
    output["入学手続期間"] = _s(r.get("enrollment_period"))
    output["都道府県"] = _s(r.get("prefecture")) or "要確認"
    output["キャンパス"] = _s(r.get("campus")) or "要確認"
    output["更新人/更新日期"] = _s(r.get("updated_by_date")) or f"AI初稿 / {datetime.now().strftime('%Y/%m/%d')}"
    return output


def normalize_extraction_result(data: dict[str, Any]) -> dict[str, Any]:
    top_level = {
        "university": data.get("university", ""),
        "admission_year": data.get("admission_year", "") or data.get("admission_period", ""),
    }
    normalized_records: list[dict[str, Any]] = []
    for raw_record in data.get("records") or []:
        if not isinstance(raw_record, dict):
            continue
        merged = {**top_level, **raw_record}
        for expanded in expand_department_rows(merged):
            normalized_records.append(normalize_record(expanded, top_level))
    return {"columns": EXCEL_COLUMNS, "records": normalized_records}


def load_and_normalize(path: str | Path) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        data = {"records": data}
    return normalize_extraction_result(data)


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize extracted admissions records to the final Excel schema.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = load_and_normalize(args.input)
    text = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
