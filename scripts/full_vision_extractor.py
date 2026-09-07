from __future__ import annotations

import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db import (  # noqa: E402
    create_source_document,
    init_db,
    insert_staging_record,
    update_source_document,
)
from scripts.json_parser import extract_json_payload  # noqa: E402
from scripts.normalize_fields import EXCEL_COLUMNS  # noqa: E402
from scripts.page_scheduler import extract_page_texts, select_vision_pages  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.quality_gate import evaluate_quality as quality_gate_evaluate  # noqa: E402
from scripts.runtime_paths import rendered_pages_dir  # noqa: E402
from scripts.table_profiles import choose_table_profile  # noqa: E402
from scripts.table_structure_extractor import (  # noqa: E402
    SymbolSummary,
    build_symbol_summaries,
    detect_table_structure,
    merge_symbol_summary_into_records,
    summarize_table_structure,
)
from scripts.validator import validate  # noqa: E402
from scripts.vision_draft_extractor import extract_with_batches as extract_vision_draft_batches  # noqa: E402


CHINESE_TO_INTERNAL = {
    "大学名称": "university",
    "入学年度": "admission_year",
    "入学时期": "admission_period",
    "学部": "faculty",
    "学科/专业": "department",
    "出愿期间": "application_period",
    "截止规则": "deadline_rule",
    "EJU场次": "eju_session",
    "EJU日语": "eju_japanese",
    "EJU综合科目": "eju_general",
    "EJU数学": "eju_math",
    "EJU物理": "eju_physics",
    "EJU化学": "eju_chemistry",
    "EJU生物": "eju_biology",
    "英语要求": "english_requirement",
    "选考方式": "screening_method",
    "选考日程": "screening_schedule",
    "合格发表日": "result_date",
    "入学手续期间": "enrollment_period",
    "都道府县": "prefecture",
    "校区": "campus",
    "置信度": "confidence",
    "是否需要复核": "needs_review",
    "风险等级": "risk_level",
    "警告/备注": "warnings",
}

INTERNAL_FIELDS = [
    "university",
    "admission_year",
    "admission_period",
    "faculty",
    "department",
    "application_period",
    "deadline_rule",
    "eju_session",
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
    "english_requirement",
    "screening_method",
    "screening_schedule",
    "result_date",
    "enrollment_period",
    "prefecture",
    "campus",
    "confidence",
    "needs_review",
    "risk_level",
    "warnings",
]

DEFAULT_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_MODEL = "gpt-4o"


def _load_env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip() or default
    return default


def _first_env(names: list[str], default: str = "") -> str:
    for name in names:
        value = _load_env_value(name, "")
        if value:
            return value
    return default


def _api_key() -> str:
    key = _first_env(["LLM_API_KEY", "OPENAI_API_KEY", "DASHSCOPE_API_KEY"])
    if not key:
        raise RuntimeError("API key not set. Use LLM_API_KEY, OPENAI_API_KEY, or DASHSCOPE_API_KEY.")
    return key


def _chat_url() -> str:
    explicit = _first_env(["OPENAI_COMPAT_URL", "LLM_COMPAT_URL", "OPENAI_URL"])
    if explicit:
        url = explicit.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"
    base = _first_env(["OPENAI_BASE_URL", "LLM_BASE_URL"])
    if base:
        url = base.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"
    return DEFAULT_CHAT_COMPLETIONS_URL


def _model() -> str:
    return _first_env(["FULL_VISION_MODEL", "OPENAI_VISION_MODEL", "LLM_MODEL"], DEFAULT_MODEL)


def _parse_page_selection(value: str) -> list[int]:
    pages: set[int] = set()
    for part in re.split(r"[,，\s]+", value.strip()):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                continue
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            pages.update(range(max(1, start), end + 1))
            continue
        if part.isdigit():
            pages.add(max(1, int(part)))
    return sorted(pages)


def _configured_pages() -> list[int] | None:
    selection = _load_env_value("FULL_VISION_PAGES", "")
    if not selection:
        return None
    pages = _parse_page_selection(selection)
    return pages or None


def _page_numbers_from_images(images: list[Path]) -> list[int]:
    numbers: list[int] = []
    for index, image in enumerate(images, 1):
        match = re.search(r"page_(\d+)", image.stem)
        numbers.append(int(match.group(1)) if match else index)
    return numbers


def _selected_pages_for_pdf(pdf_path: Path) -> list[int] | None:
    configured = _configured_pages()
    if configured:
        return configured
    max_pages = max(1, int(_load_env_value("FULL_VISION_MAX_PAGES", "12") or "12"))
    return select_vision_pages(pdf_path, max_pages=max_pages)


def _table_structure_analysis(images: list[Path], university: str, text_sample: str = "") -> tuple[list[str], dict[str, SymbolSummary]]:
    profile = choose_table_profile(university=university, text_sample=text_sample)
    if profile is None:
        return [], {}
    warnings: list[str] = []
    summaries: dict[str, SymbolSummary] = {}
    for image in images:
        match = re.search(r"page_(\d+)", image.stem)
        page_number = int(match.group(1)) if match else 0
        if page_number != 5:
            continue
        try:
            structure = detect_table_structure(image, profile)
        except Exception as exc:
            warnings.append(f"Page 5 宽表结构检测失败：{exc}")
            continue
        summaries.update(build_symbol_summaries(structure, profile))
        warnings.extend(summarize_table_structure(structure, profile))
        if not warnings:
            warnings.append(
                f"Page 5 宽表已完成结构检测：{len(structure.row_bands)} 个行带、{len(structure.vertical_lines)} 条竖线；理工科字段仍建议人工复核。"
            )
    return warnings, summaries


def merge_table_structure_enhancement(
    chinese_records: list[dict[str, Any]],
    summaries: dict[str, SymbolSummary],
    global_fields: dict[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not summaries:
        return chinese_records, []
    global_fields = global_fields or {}
    department_summaries = {
        key: summary
        for key, summary in summaries.items()
        if "||" in key and summary.department
    }
    if department_summaries:
        profile_faculties = {summary.faculty for summary in department_summaries.values()}
        model_by_exact: dict[tuple[str, str], dict[str, Any]] = {}
        model_by_faculty: dict[str, dict[str, Any]] = {}
        existing_exact = set()
        for record in chinese_records:
            faculty = _text(record.get("学部") or record.get("faculty"))
            department = _text(record.get("学科/专业") or record.get("department"))
            if faculty not in profile_faculties:
                continue
            if department:
                model_by_exact.setdefault((faculty, department), record)
                existing_exact.add((faculty, department))
            model_by_faculty.setdefault(faculty, record)

        primary_records: list[dict[str, Any]] = []
        added_count = 0
        for summary in department_summaries.values():
            record = {column: "" for column in EXCEL_COLUMNS}
            exact_source = model_by_exact.get((summary.faculty, summary.department)) or {}
            faculty_source = model_by_faculty.get(summary.faculty) or {}
            source = {**faculty_source, **{key: value for key, value in exact_source.items() if _text(value)}}
            for column in EXCEL_COLUMNS:
                if _text(source.get(column)):
                    record[column] = _text(source.get(column))
            for key, column in CHINESE_TO_INTERNAL.items():
                if _text(source.get(column)) and not _text(record.get(key)):
                    record[key] = _text(source.get(column))
            for column in GLOBAL_BACKFILL_COLUMNS:
                if _text(global_fields.get(column)):
                    record[column] = _text(global_fields.get(column))
            record["学部"] = summary.faculty
            record["学科/专业"] = summary.department
            record["是否需要复核"] = "是"
            record["风险等级"] = record.get("风险等级") or "medium"
            record["警告/备注"] = record.get("警告/备注") or "Page 5结构增强主记录源，请人工复核"
            primary_records.append(record)
            if (summary.faculty, summary.department) not in existing_exact:
                added_count += 1
        preserved_records = [
            dict(record)
            for record in chinese_records
            if _text(record.get("学部") or record.get("faculty")) not in profile_faculties
        ]
        base_records = preserved_records + primary_records
        merged = merge_symbol_summary_into_records(base_records, summaries)
        changed = sum(1 for before, after in zip(base_records, merged) if before != after)
        warnings = [f"Page 5结构增强以profile为主记录源生成 {len(primary_records)} 条记录"]
        if changed:
            warnings.append(f"Page 5结构增强已覆盖 {changed} 条记录的EJU/英语字段")
        if added_count:
            warnings.append(f"Page 5结构增强补充 {added_count} 条缺失记录")
        return merged, warnings

    existing_keys = {
        (
            _text(record.get("学部") or record.get("faculty")),
            _text(record.get("学科/专业") or record.get("department")),
        )
        for record in chinese_records
    }
    added_records: list[dict[str, Any]] = []
    for _summary_key, summary in summaries.items():
        key = (summary.faculty, summary.department)
        if key in existing_keys:
            continue
        record = {column: "" for column in EXCEL_COLUMNS}
        for column in GLOBAL_BACKFILL_COLUMNS:
            if _text(global_fields.get(column)):
                record[column] = _text(global_fields.get(column))
        record["学部"] = summary.faculty
        record["学科/专业"] = summary.department
        record["是否需要复核"] = "是"
        record["风险等级"] = "medium"
        record["警告/备注"] = "Page 5结构增强补充记录，请人工复核"
        added_records.append(record)
        existing_keys.add(key)
    base_records = chinese_records + added_records
    merged = merge_symbol_summary_into_records(base_records, summaries)
    changed = sum(1 for before, after in zip(base_records, merged) if before != after)
    warnings = []
    if changed:
        warnings.append(f"Page 5结构增强已覆盖 {changed} 条记录的EJU/英语字段")
    if added_records:
        warnings.append(f"Page 5结构增强补充 {len(added_records)} 条缺失记录")
    return merged, warnings


def extract_global_fields_from_pdf_texts(page_texts: list[str]) -> dict[str, str]:
    joined = "\n".join(page_texts)
    compact = re.sub(r"\s+", "", joined)
    fields: dict[str, str] = {}
    eju_match = re.search(r"(20\d{2}年\d{1,2}月回)または(20\d{2}年\d{1,2}月回)", compact)
    if eju_match:
        fields["EJU场次"] = f"{eju_match.group(1)}または{eju_match.group(2)}"
    period_match = re.search(
        r"出願期間(20\d{2}年\d{1,2}月\d{1,2}日\([^)]+\)10:00[～〜~]?\d{1,2}月\d{1,2}日\([^)]+\)17:00)",
        compact,
    )
    if period_match:
        fields["出愿期间"] = period_match.group(1)
    return fields


def merge_deterministic_global_fields(model_fields: dict[str, Any], deterministic_fields: dict[str, Any]) -> dict[str, Any]:
    merged = dict(model_fields)
    for key, value in deterministic_fields.items():
        text = _text(value)
        if text:
            merged[key] = text
    return merged


def build_prompt(university: str = "", year: str = "", page_note: str = "") -> str:
    hints = []
    if university:
        hints.append(f"大学名称提示：{university}")
    if year:
        hints.append(f"入学年度提示：{year}")
    hint_text = "\n".join(hints)
    columns = "、".join(EXCEL_COLUMNS)
    return f"""你是一名日本大学招生要项抽取员。请把上传的整份 PDF 从头到尾读一遍，不要只看局部截图，也不要只依赖目录页。
{hint_text}
{page_note}

目标：把“外国学生/留学生本科招生要项”整理成固定中文字段表格。

工作规则：
1. 先完整浏览 PDF，判断目录页、说明页、样例页、正文表格页分别是什么角色。
2. 不要从目录页创建记录，“出願期間前”“出願期間中”“出願期間後”“合格後”等章节标题绝不能当作学部。
3. “募集学部・学科・募集人員”页只作为学部/学科名称参考；如果该页没有 EJU、英语、选考方式、选考日程等入试条件，不要单独为它创建记录。
4. “出愿期间”只能填写明确标注为“出願期間”的日期；不要把試験日、選考日、合格発表日、入学手続日误填为出愿期间。
5. 对宽表格要先理解表头、符号、合并单元格、学部与学科层级，再整理记录。
6. 记录粒度是实际招生单位：同一学部被拆成多个视觉行时，如果不是不同学科/专业，不要重复导出；不同学科/专业需要分别导出。
7. 学部名、学科/专业名保留日文原文，不要翻译。
8. 能从全局页面继承的信息要继承到每条记录，例如出愿期间、截止规则、EJU场次。
9. 看不清时不要猜，把不确定性写进“警告/备注”，但不要整列无依据地填“要确认”。
10. 最终 JSON 中每条记录必须包含以下 25 个中文字段，字段名和顺序必须稳定：
{columns}

输出要求：
- 只返回 JSON，不要 Markdown。
- JSON 形状必须为 {{"quality_summary":"", "global_fields":{{}}, "records":[...]}}。
- 如果当前页面里出现出愿期间、截止规则、EJU场次等全局信息，请写入 global_fields；后续程序会把它回填到所有记录。
- records 内每个对象都必须包含上述 25 个中文字段。"""


def _image_data_url(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    data = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{data}"


def _call_llm(image_paths: list[Path], university: str, year: str, page_numbers: list[int] | None = None) -> tuple[str, str]:
    if os.environ.get("ADMISSIONS_DISABLE_MODEL_CALLS") == "1":
        raise RuntimeError("本地演示不调用模型 API。请由 Codex 阅读 PDF 后导入结构化结果，再进行人工复核。")
    page_numbers = page_numbers or list(range(1, len(image_paths) + 1))
    if page_numbers:
        page_note = "当前请求包含 PDF 第 " + "、".join(str(page) for page in page_numbers) + " 页。请只抽取这些页面中真实出现的招生记录；全局信息写入 global_fields。"
    else:
        page_note = "当前请求包含 PDF 的若干页面。请只抽取这些页面中真实出现的招生记录；全局信息写入 global_fields。"
    content: list[dict[str, Any]] = [{"type": "text", "text": build_prompt(university, year, page_note)}]
    for offset, image_path in enumerate(image_paths):
        page_label = page_numbers[offset] if offset < len(page_numbers) else offset + 1
        content.append({"type": "text", "text": f"PDF page {page_label}"})
        content.append({"type": "image_url", "image_url": {"url": _image_data_url(image_path)}})

    payload = {
        "model": _model(),
        "messages": [{"role": "user", "content": content}],
        "temperature": 0,
        "max_tokens": int(_load_env_value("FULL_VISION_MAX_TOKENS", "16000") or "16000"),
    }
    req = urllib_request.Request(
        _chat_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {_api_key()}"},
        method="POST",
    )
    try:
        with urllib_request.urlopen(req, timeout=int(_load_env_value("FULL_VISION_TIMEOUT_SECONDS", "300") or "300")) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API error {exc.code}: {body}") from exc

    choice = raw.get("choices", [{}])[0]
    message = choice.get("message", {})
    text = message.get("content", "")
    if isinstance(text, list):
        text = "\n".join(str(part.get("text", "")) if isinstance(part, dict) else str(part) for part in text)
    return str(text), str(choice.get("finish_reason") or "")


def parse_model_response(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("["):
        records = json.loads(stripped)
        return {"records": records}
    try:
        parsed = extract_json_payload(stripped)
    except ValueError:
        array_match = re.search(r"\[[\s\S]*\]", stripped)
        if not array_match:
            raise
        records = json.loads(array_match.group(0))
        return {"records": records}
    if isinstance(parsed, dict) and isinstance(parsed.get("records"), list):
        return parsed
    if isinstance(parsed, list):
        return {"records": parsed}
    raise ValueError("Model response JSON must contain records")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _merge_global_fields(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key in EXCEL_COLUMNS:
        value = _text(incoming.get(key))
        if value and not _text(merged.get(key)):
            merged[key] = value
    for key, value in incoming.items():
        if key in EXCEL_COLUMNS:
            continue
        text = _text(value)
        if text and not _text(merged.get(key)):
            merged[key] = text
    return merged


GLOBAL_BACKFILL_COLUMNS = ["大学名称", "入学年度", "入学时期", "出愿期间", "截止规则", "EJU场次", "都道府县", "校区"]
GLOBAL_OVERRIDE_COLUMNS = {"大学名称", "入学年度", "入学时期", "出愿期间", "截止规则", "EJU场次", "都道府县", "校区"}
WEAK_TEXT_MARKERS = ["无明确说明", "需参考官网", "要确认", "要確認", "根据学科要求", "具体依学部", "不明"]


def _is_weak_value(value: Any) -> bool:
    text = _text(value)
    return not text or any(marker in text for marker in WEAK_TEXT_MARKERS)


def apply_global_fields(chinese_records: list[dict[str, Any]], global_fields: dict[str, Any]) -> list[dict[str, Any]]:
    filled: list[dict[str, Any]] = []
    for record in chinese_records:
        next_record = dict(record)
        for column in GLOBAL_BACKFILL_COLUMNS:
            global_value = _text(global_fields.get(column))
            if not global_value:
                continue
            if column in GLOBAL_OVERRIDE_COLUMNS or _is_weak_value(next_record.get(column)):
                next_record[column] = global_value
            elif not _text(next_record.get(column)):
                next_record[column] = _text(global_fields.get(column))
        for column in EXCEL_COLUMNS:
            next_record.setdefault(column, "")
        filled.append(next_record)
    return filled


def _record_score(record: dict[str, Any]) -> int:
    score = 0
    for column in EXCEL_COLUMNS:
        value = _text(record.get(column))
        if value:
            score += 1
    evidence = " ".join(_text(record.get(column)) for column in ["EJU场次", "英语要求", "选考方式", "选考日程", "合格发表日"])
    for marker in ["TOEFL", "IELTS", "TOEIC", "2025年11月", "2026年6月", "面接", "書類", "オンライン"]:
        if marker in evidence:
            score += 3
    weak_count = sum(1 for column in ["英语要求", "EJU物理", "EJU化学", "EJU生物", "选考方式"] if _is_weak_value(record.get(column)))
    return score - weak_count


def _is_summary_like(record: dict[str, Any]) -> bool:
    english = _text(record.get("英语要求"))
    screening = _text(record.get("选考方式"))
    eju_values = " ".join(_text(record.get(column)) for column in ["EJU日语", "EJU综合科目", "EJU数学", "EJU物理", "EJU化学", "EJU生物"])
    if any(marker in english for marker in ["无明确说明", "需参考官网", "要确认", "要確認"]):
        return True
    if "具体依学部" in screening:
        return True
    return "根据学科要求" in eju_values


def _drop_weaker_faculty_summaries(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_faculty: dict[str, list[dict[str, Any]]] = {}
    for record in records:
        faculty = _text(record.get("学部"))
        by_faculty.setdefault(faculty, []).append(record)

    output: list[dict[str, Any]] = []
    for faculty, group in by_faculty.items():
        if not faculty or len(group) == 1:
            output.extend(group)
            continue
        best_specific_score = max((_record_score(item) for item in group if not _is_summary_like(item)), default=-999)
        for item in group:
            if _is_summary_like(item) and best_specific_score >= _record_score(item) + 4:
                continue
            output.append(item)
    return output


def _dedupe_chinese_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for record in records:
        key = (
            _text(record.get("大学名称")),
            _text(record.get("入学年度")),
            _text(record.get("学部")),
            _text(record.get("学科/专业")),
        )
        if key not in deduped:
            deduped[key] = dict(record)
            continue
        current = deduped[key]
        for column in EXCEL_COLUMNS:
            if not _text(current.get(column)) and _text(record.get(column)):
                current[column] = record.get(column)
    return _drop_weaker_faculty_summaries(list(deduped.values()))


def _extract_with_batches(images: list[Path], university: str, year: str) -> tuple[list[dict[str, Any]], dict[str, Any], str]:
    batch_size = max(1, int(_load_env_value("FULL_VISION_BATCH_PAGES", "4") or "4"))
    draft = extract_vision_draft_batches(
        images,
        university=university,
        year=year,
        batch_size=batch_size,
        call_llm=_call_llm,
        parse_model_response=parse_model_response,
        merge_global_fields=_merge_global_fields,
        apply_global_fields=apply_global_fields,
        dedupe_records=_dedupe_chinese_records,
    )
    return draft.records, draft.global_fields, draft.finish_reason


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    text = str(value or "").strip().lower()
    return text in {"是", "yes", "true", "1", "需要", "要"}


def _warnings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    text = str(value or "").strip()
    if not text:
        return []
    return [part.strip() for part in re.split(r"[；;\n]+", text) if part.strip()]


def to_internal_records(chinese_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for item in chinese_records:
        record: dict[str, Any] = {field: "" for field in INTERNAL_FIELDS}
        for zh, internal in CHINESE_TO_INTERNAL.items():
            value = item.get(zh, "")
            if internal == "needs_review":
                record[internal] = _as_bool(value)
            elif internal == "warnings":
                record[internal] = _warnings(value)
            elif internal == "confidence":
                try:
                    record[internal] = float(value or 0)
                except Exception:
                    record[internal] = 0.0
            else:
                record[internal] = str(value or "").strip()
        if not record["admission_period"]:
            record["admission_period"] = "全一回"
        if not record["risk_level"]:
            record["risk_level"] = "medium"
        output.append(record)
    return output


def evaluate_quality(
    chinese_records: list[dict[str, Any]],
    parse_error: str = "",
    finish_reason: str = "",
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    return quality_gate_evaluate(
        chinese_records,
        to_internal_records=to_internal_records,
        parse_error=parse_error,
        finish_reason=finish_reason,
        extra_warnings=extra_warnings,
    )


def run_extraction(pdf_path: Path, university: str, year: str, url: str = "") -> dict[str, Any]:
    if os.environ.get("ADMISSIONS_DISABLE_MODEL_CALLS") == "1":
        raise RuntimeError("本地演示使用 Codex 直接阅读 PDF 后导入的数据，不启动外部模型抽取。")
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")
    init_db()
    doc_id = create_source_document(
        university=university or "待识别",
        file_name=pdf_path.name,
        file_path=str(pdf_path),
        pdf_url=url or "",
        admission_year=str(year),
    )
    out_dir = rendered_pages_dir() / f"full_vision_{doc_id}"
    selected_pages = _selected_pages_for_pdf(pdf_path)
    page_texts = extract_page_texts(pdf_path)
    text_sample = "\n".join(page_texts[:5])
    deterministic_global_fields = extract_global_fields_from_pdf_texts(page_texts)
    images = render_pdf_to_images(
        pdf_path,
        out_dir,
        dpi=int(_load_env_value("FULL_VISION_DPI", "180") or "180"),
        pages=selected_pages,
    )
    structure_warnings, symbol_summaries = _table_structure_analysis(images, university, text_sample=text_sample)

    try:
        chinese_records, _global_fields, finish_reason = _extract_with_batches(images, university, str(year))
        _global_fields = merge_deterministic_global_fields(_global_fields, deterministic_global_fields)
        chinese_records = apply_global_fields(chinese_records, _global_fields)
        chinese_records, enhancement_warnings = merge_table_structure_enhancement(
            chinese_records,
            symbol_summaries,
            global_fields=_global_fields,
        )
        quality = evaluate_quality(
            chinese_records,
            finish_reason=finish_reason,
            extra_warnings=structure_warnings + enhancement_warnings,
        )
    except Exception as exc:
        quality = evaluate_quality([], parse_error=str(exc))
        update_source_document(doc_id, status="failed")
        return {
            "doc_id": doc_id,
            "status": "failed",
            "university": university or "",
            "records": 0,
            "inserted": 0,
            "pages": len(images),
            "selected_pages": selected_pages or [],
            "failed_pages": [],
            **quality,
        }

    internal_records = to_internal_records(chinese_records)
    inserted = 0
    final_university = university or ""
    for record in internal_records:
        if university and not record.get("university"):
            record["university"] = university
        if year and not record.get("admission_year"):
            record["admission_year"] = str(year)
        if not final_university and record.get("university"):
            final_university = str(record.get("university"))
        validated = validate(record)
        if quality["quality_status"] != "ok":
            validated["needs_review"] = True
            validated["risk_level"] = "high" if quality["quality_status"] == "failed" else validated.get("risk_level", "medium")
            merged_warnings = list(validated.get("warnings_json") or [])
            for warning in quality.get("warnings", []):
                if warning not in merged_warnings:
                    merged_warnings.append(warning)
            validated["warnings_json"] = merged_warnings
        insert_staging_record(doc_id, None, validated)
        inserted += 1

    update_source_document(
        doc_id,
        status="vision_completed" if inserted else "failed",
        university=final_university or "待识别",
    )
    return {
        "doc_id": doc_id,
        "status": "vision_completed" if inserted else "failed",
        "university": final_university or "",
        "records": len(internal_records),
        "inserted": inserted,
        "pages": len(images),
        "selected_pages": selected_pages or [],
        "failed_pages": [],
        **quality,
    }
