from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db import (  # noqa: E402
    create_source_document,
    init_db,
    insert_staging_record,
    prune_duplicate_documents,
    update_source_document,
)
from scripts.json_parser import extract_json_payload  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.validator import normalize_field_evidence, validate  # noqa: E402

PROMPT_PATH = ROOT / "prompts" / "field_extraction_prompt.md"
DEFAULT_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TEXT_MODEL = "gpt-4o-mini"
DEFAULT_VISION_MODEL = "gpt-4o-mini"

TOP_LEVEL_FIELDS = [
    "university",
    "admission_year",
    "admission_system",
    "application_period",
    "deadline_rule",
]

RECORD_FIELDS = [
    "faculty",
    "department",
    "application_period",
    "deadline_rule",
    "japanese_exam",
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
    "warnings",
    "field_evidence",
]

EVIDENCE_FIELDS = [
    "application_period",
    "deadline_rule",
    "japanese_exam",
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
]

FIELD_KEYWORDS: dict[str, tuple[str, ...]] = {
    "application_period": ("出願期間", "出願受付", "受付期間"),
    "deadline_rule": ("必着", "消印有効", "期限内到着", "直送", "TAO", "アップロード", "入学検定料", "支払い"),
    "japanese_exam": ("日本留学試験", "EJU", "JLPT", "日本語能力試験"),
    "eju_session": ("EJU", "日本留学試験", "11月回", "6月回", "第1回", "第2回"),
    "eju_japanese": ("日本語",),
    "eju_general": ("総合科目",),
    "eju_math": ("数学", "コース1", "コース2"),
    "eju_physics": ("物理",),
    "eju_chemistry": ("化学",),
    "eju_biology": ("生物",),
    "english_requirement": ("TOEFL", "IELTS", "TOEIC", "英語外部試験", "外国語外部試験"),
    "screening_method": ("選考方法", "書類選考", "小論文", "面接", "口頭試問", "学力試験"),
    "screening_schedule": ("選考日", "試験日", "面接日", "選考日程"),
    "result_date": ("合格発表", "結果通知", "発表日"),
    "enrollment_period": ("入学手続", "手続期間", "入学手続期間"),
    "prefecture": ("都", "道", "府", "県"),
    "campus": ("キャンパス",),
}

PAGE_SCORE_KEYWORDS: tuple[str, ...] = (
    "出願期間",
    "選考方法",
    "入学試験日程",
    "EJU",
    "日本留学試験",
    "TOEFL",
    "IELTS",
    "TOEIC",
    "合格発表",
    "入学手続",
    "必着",
    "消印有効",
)

UNIVERSITY_RE = re.compile(r"([一-龥ぁ-んァ-ヴーA-Za-z・･ー\-\s]{2,40}大学)")
YEAR_RE = re.compile(r"(20\d{2})\s*年度")
SYSTEM_RE = re.compile(r"(外国学生のための学部入学試験|私費外国人留学生[^\n]{0,30}入学試験|外国人留学生[^\n]{0,30}入学試験)")
DATE_RANGE_RE = re.compile(
    r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日[^\n]{0,80}?[～〜-][^\n]{0,80}?\d{1,2}\s*月\s*\d{1,2}\s*日[^\n]{0,40})"
)

PAGE_SCORE_WEIGHTS: dict[str, int] = {
    "出願期間": 5,
    "出願受付": 4,
    "選考方法": 4,
    "選抜方法": 4,
    "選考日程": 4,
    "試験日": 3,
    "合格発表": 5,
    "入学手続": 5,
    "必着": 5,
    "消印有効": 5,
    "期限内到着": 5,
    "TAO": 4,
    "EJU": 4,
    "日本留学試験": 4,
    "TOEFL": 4,
    "IELTS": 4,
    "TOEIC": 4,
    "学部": 2,
    "学科": 2,
    "専攻": 2,
    "専修": 2,
}

TABLE_SIGNAL_TOKENS: tuple[str, ...] = (
    "学部",
    "学科",
    "専攻",
    "専修",
    "コース",
    "EJU",
    "日本留学試験",
    "TOEFL",
    "IELTS",
    "TOEIC",
    "選考方法",
    "選考日程",
    "合格発表",
    "入学手続",
)

DEADLINE_RULE_MARKERS: tuple[str, ...] = (
    "必着",
    "消印有効",
    "期限内到着",
    "TAO完了",
    "直送期限",
    "upload deadline",
    "payment deadline",
    "出願締切",
    "締切",
)

ENGLISH_TEST_MARKERS: tuple[str, ...] = ("TOEFL", "IELTS", "TOEIC")
EJU_SUBJECT_LABELS: dict[str, tuple[str, ...]] = {
    "eju_japanese": ("日本語",),
    "eju_general": ("総合科目",),
    "eju_math": ("数学", "コース1", "コース2"),
    "eju_physics": ("物理",),
    "eju_chemistry": ("化学",),
    "eju_biology": ("生物",),
}

REQUIREMENT_FIELDS: tuple[str, ...] = (
    "application_period",
    "deadline_rule",
    "japanese_exam",
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
)

TABLE_PATCH_PROMPT = """
You are reading cropped images from a Japanese university admissions table.
Return strict JSON only. Do not return markdown.

Goal:
- Enumerate every visible faculty / department admissions row in this crop.
- Preserve 学部一括 / 学科一括 wording when that is what the table shows.
- Do not collapse multiple visible rows into one.
- If one visible row lists multiple departments under one shared requirement set, keep them in one record and join the department names.
- Do not invent rows that are not visible.

Return:
{
  "records": [
    {
      "faculty": "",
      "department": "",
      "application_period": "",
      "deadline_rule": "",
      "japanese_exam": "",
      "eju_session": "",
      "eju_japanese": "",
      "eju_general": "",
      "eju_math": "",
      "eju_physics": "",
      "eju_chemistry": "",
      "eju_biology": "",
      "english_requirement": "",
      "screening_method": "",
      "screening_schedule": "",
      "result_date": "",
      "enrollment_period": "",
      "prefecture": "",
      "campus": "",
      "confidence": 0.0,
      "needs_review": true,
      "warnings": [],
      "field_evidence": {}
    }
  ]
}

Rules:
- deadline_rule should capture 必着 / 消印有効 / 期限内到着 / TAO完了 / 直送期限 when visible.
- Do not put TOEFL / IELTS / TOEIC into EJU fields.
- Do not put EJU subjects into english_requirement.
- If unclear, leave the field empty and add a short warning.
"""

SYMBOL_ABSTRACTION_PROMPT = """
You are reading a Japanese university admissions table from a full page image plus optional zoom crops.
Return strict JSON only. Do not return markdown.

Goal:
- Extract the table as symbol rows before turning symbols into final admissions fields.
- The full page image is the primary evidence. Crops are only zoom support.
- Never interpret isolated crops without the full page headers, notes, and footnotes.
- Preserve row alignment: faculty / department labels must match the same row as the symbols.
- Preserve 学部一括 / 学科一括 exactly when shown.
- If one visible row lists multiple departments under one shared requirement set, keep them in one symbol row.
- Do not invent departments that are not visible.

Return:
{
  "symbol_rows": [
    {
      "faculty": "",
      "department": "",
      "page": null,
      "symbols": {
        "日本語": "",
        "総合科目": "",
        "数学コース1": "",
        "数学コース2": "",
        "物理": "",
        "化学": "",
        "生物": "",
        "TOEFL iBT": "",
        "IELTS Academic Module": "",
        "TOEIC L&R": "",
        "ドイツ語": "",
        "フランス語": "",
        "書類選考": "",
        "小論文": "",
        "学力試験": "",
        "面接": "",
        "口頭試問": ""
      },
      "notes": [],
      "evidence_text": ""
    }
  ]
}

Rules:
- Copy symbols exactly as shown: ○, ◯, ◎, △, ▲, ※, 注, blank, etc.
- If a cell contains △, ※, 注, footnote marks, or conditional symbols, search the full page and nearby text for the explanation and include it in notes.
- Empty cells must stay empty.
- Do not convert symbols into final field values. The program will do that after your JSON.
- Do not put TOEFL / IELTS / TOEIC into EJU columns.
- Do not put EJU subjects into English-test columns.
"""


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                return line.split("=", 1)[1].strip()
    return default


def _first_env(names: list[str], default: str = "") -> str:
    for name in names:
        value = _load_env_value(name, "")
        if value:
            return value
    return default


def _api_key() -> str:
    key = _first_env(["LLM_API_KEY", "OPENAI_API_KEY"])
    if not key:
        raise RuntimeError("API key not set. Use LLM_API_KEY or OPENAI_API_KEY.")
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


def _call_llm(
    messages: list[dict[str, Any]],
    model: str,
    *,
    max_tokens: int = 9000,
    timeout_seconds: int = 180,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        "max_tokens": max_tokens,
    }
    req = urllib_request.Request(
        _chat_url(),
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {_api_key()}",
        },
        method="POST",
    )
    last_error: Exception | None = None
    for attempt in range(2):
        try:
            with urllib_request.urlopen(req, timeout=timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            text = raw["choices"][0]["message"]["content"]
            result = extract_json_payload(text)
            result["_raw_response"] = text
            result["_usage"] = raw.get("usage", {})
            return result
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            last_error = RuntimeError(f"LLM API error {exc.code}: {body}")
            if exc.code == 429 and attempt == 0:
                continue
            raise last_error
        except Exception as exc:
            last_error = exc
            if attempt == 0:
                continue
            raise
    raise last_error or RuntimeError("LLM request failed")


def _clean_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _normalize_list_delimiters(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    text = re.sub(r"\s*[;,，]\s*", "、", text)
    text = re.sub(r"\s*／\s*|\s*/\s*", " / ", text)
    text = re.sub(r"\s*・\s*", "・", text)
    text = re.sub(r"、{2,}", "、", text)
    return text.strip("、 ")


def _normalize_department_value(value: str) -> str:
    text = _normalize_list_delimiters(value)
    if not text:
        return ""
    text = re.sub(r"学系\s*([0-9０-９])\s*[－-][^、/]+", lambda m: f"学系{m.group(1)}", text)
    text = re.sub(r"\s*、\s*", "、", text)
    return text


def _clean_university(value: str) -> str:
    match = UNIVERSITY_RE.search(str(value or ""))
    if not match:
        return _clean_text(value)
    return re.sub(r"\s+", "", match.group(1))


def _fallback_university(page_texts: dict[int, str], pdf_path: Path) -> str:
    probe = "\n".join(page_texts.get(i, "") for i in range(1, min(len(page_texts), 3) + 1))
    for source in (probe, pdf_path.stem):
        match = UNIVERSITY_RE.search(source)
        if match:
            return _clean_university(match.group(1))
    return ""


def _fallback_year(page_texts: dict[int, str]) -> str:
    probe = "\n".join(page_texts.get(i, "") for i in range(1, min(len(page_texts), 3) + 1))
    match = YEAR_RE.search(probe)
    return f"{match.group(1)}年度" if match else ""


def _fallback_system(page_texts: dict[int, str]) -> str:
    probe = "\n".join(page_texts.get(i, "") for i in range(1, min(len(page_texts), 5) + 1))
    match = SYSTEM_RE.search(probe)
    return _clean_text(match.group(1)) if match else ""


def _fallback_application_period(page_texts: dict[int, str]) -> str:
    for _, text in page_texts.items():
        if "出願期間" not in text and "受付期間" not in text:
            continue
        match = DATE_RANGE_RE.search(text)
        if match:
            return _clean_text(match.group(1))
    return ""


def _fallback_deadline_rule(page_texts: dict[int, str]) -> str:
    snippets: list[str] = []
    for _, text in page_texts.items():
        for line in text.splitlines():
            stripped = _clean_text(line)
            if not stripped:
                continue
            if any(marker in stripped for marker in FIELD_KEYWORDS["deadline_rule"]):
                snippets.append(stripped)
    deduped = list(dict.fromkeys(snippets))
    return " / ".join(deduped[:4])


def _page_score(text: str) -> int:
    if not text.strip():
        return -99
    score = 0
    for token, weight in PAGE_SCORE_WEIGHTS.items():
        if token in text:
            score += weight
    if "目次" in text:
        score -= 8
    if "参照" in text and "ページ" in text:
        score -= 3
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if len(lines) >= 10 and any(token in text for token in TABLE_SIGNAL_TOKENS):
        score += 3
    if len(text.strip()) < 900 and any(token in text for token in ("EJU", "日本留学試験", "学部", "選考方法")):
        score += 2
    return score


def _page_is_table_heavy(text: str) -> bool:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    token_hits = sum(1 for token in TABLE_SIGNAL_TOKENS if token in text)
    return (
        token_hits >= 3
        or ("学部" in text and "学科" in text)
        or (token_hits >= 1 and len(lines) >= 14)
        or (token_hits >= 2 and len(text.strip()) < 1200)
    )


def _candidate_pages(page_texts: dict[int, str], max_pages: int) -> list[int]:
    ranked = sorted(
        page_texts.items(),
        key=lambda item: (_page_score(item[1]), -item[0]),
        reverse=True,
    )
    pages = [page for page in [1, 2] if page in page_texts]
    for page_num, _ in ranked:
        if page_num not in pages and _page_score(page_texts.get(page_num, "")) > 0:
            pages.append(page_num)
        if len(pages) >= max_pages:
            break
    return sorted(dict.fromkeys(page for page in pages if page in page_texts))


def _table_support_pages(page_texts: dict[int, str], candidate_pages: list[int], max_pages: int) -> list[int]:
    ranked = sorted(
        (
            (page_num, _page_score(text))
            for page_num, text in page_texts.items()
            if _page_is_table_heavy(text)
        ),
        key=lambda item: (item[1], -item[0]),
        reverse=True,
    )
    pages = [page for page in candidate_pages if _page_is_table_heavy(page_texts.get(page, ""))]
    for page_num, score in ranked:
        if score <= 0:
            continue
        if page_num not in pages:
            pages.append(page_num)
        if len(pages) >= max_pages:
            break
    return sorted(dict.fromkeys(pages))


def _build_text_context(page_texts: dict[int, str], candidate_pages: list[int], max_chars: int = 90000) -> str:
    all_sections = [f"=== PAGE {page} ===\n{text}" for page, text in sorted(page_texts.items()) if text.strip()]
    full_text = "\n\n".join(all_sections)
    if len(full_text) <= max_chars:
        return full_text

    preferred_pages = sorted(dict.fromkeys([1, 2, 3] + candidate_pages))
    sections: list[str] = []
    for page in preferred_pages:
        text = page_texts.get(page, "")
        if text.strip():
            sections.append(f"=== PAGE {page} ===\n{text}")
    compact = "\n\n".join(sections)
    return compact[:max_chars]


def _image_data_url(path: Path) -> str:
    b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
    return f"data:image/png;base64,{b64}"


def _render_candidate_images(pdf_path: Path, output_dir: Path, pages: list[int]) -> list[Path]:
    if not pages:
        return []
    output_dir.mkdir(parents=True, exist_ok=True)
    return render_pdf_to_images(pdf_path, output_dir, dpi=220, pages=pages)


def _table_image_variants(image_path: Path, out_dir: Path) -> list[tuple[str, list[Path]]]:
    variants: list[tuple[str, list[Path]]] = [("full_page", [image_path])]
    try:
        from PIL import Image

        out_dir.mkdir(parents=True, exist_ok=True)
        with Image.open(image_path) as img:
            width, height = img.size
            if height < 1400:
                return variants
            resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS", Image.LANCZOS)
            crop_top = max(int(height * 0.12), 240)
            anchor_x2 = max(int(width * 0.36), min(width, 900))
            bands = [
                (crop_top, int(height * 0.42), "table_top"),
                (int(height * 0.34), int(height * 0.68), "table_middle"),
                (int(height * 0.60), int(height * 0.94), "table_bottom"),
            ]
            for y1, y2, name in bands:
                top = max(0, min(y1, height - 10))
                bottom = max(top + 10, min(y2, height))
                if bottom - top < 200:
                    continue
                focus_path = out_dir / f"{image_path.stem}_{name}.png"
                focus_crop = img.crop((0, top, width, bottom))
                if focus_crop.width < 1200:
                    focus_crop = focus_crop.resize(
                        (int(focus_crop.width * 1.8), int(focus_crop.height * 1.8)),
                        resample,
                    )
                focus_crop.save(focus_path, format="PNG", optimize=True)

                anchor_path = out_dir / f"{image_path.stem}_{name}_anchor.png"
                anchor_crop = img.crop((0, top, anchor_x2, bottom))
                if anchor_crop.width < 900:
                    anchor_crop = anchor_crop.resize(
                        (int(anchor_crop.width * 2.0), int(anchor_crop.height * 2.0)),
                        resample,
                    )
                anchor_crop.save(anchor_path, format="PNG", optimize=True)
                variants.append((name, [image_path, focus_path, anchor_path]))
    except Exception:
        return variants
    return variants


def _empty_evidence() -> dict[str, dict[str, Any]]:
    return {field: {"text": "", "page": None} for field in EVIDENCE_FIELDS}


def _find_field_evidence(field: str, value: str, page_texts: dict[int, str]) -> dict[str, Any]:
    if not value and field not in FIELD_KEYWORDS:
        return {"text": "", "page": None}
    candidates = [value] if value else []
    candidates.extend(FIELD_KEYWORDS.get(field, ()))
    for page_num, text in page_texts.items():
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        for line_idx, line in enumerate(lines):
            if any(candidate and candidate in line for candidate in candidates):
                snippet = line
                if line_idx + 1 < len(lines) and len(snippet) < 120:
                    snippet = f"{snippet} {lines[line_idx + 1]}"
                return {"text": snippet[:220], "page": page_num}
    return {"text": value or "", "page": None}


def _exact_record_shape() -> dict[str, Any]:
    return {
        "faculty": "",
        "department": "",
        "application_period": "",
        "deadline_rule": "",
        "japanese_exam": "",
        "eju_session": "",
        "eju_japanese": "",
        "eju_general": "",
        "eju_math": "",
        "eju_physics": "",
        "eju_chemistry": "",
        "eju_biology": "",
        "english_requirement": "",
        "screening_method": "",
        "screening_schedule": "",
        "result_date": "",
        "enrollment_period": "",
        "prefecture": "",
        "campus": "",
        "confidence": 0.0,
        "needs_review": True,
        "warnings": [],
        "field_evidence": _empty_evidence(),
    }


def _normalize_deadline_rule(value: str) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    snippets: list[str] = []
    for marker in DEADLINE_RULE_MARKERS:
        if marker in text:
            line_match = re.search(rf"([^\n。]{0,40}{re.escape(marker)}[^\n。]{{0,40}})", text, re.IGNORECASE)
            if line_match:
                snippets.append(_clean_text(line_match.group(1)))
            else:
                snippets.append(marker)
    if snippets:
        return " / ".join(dict.fromkeys(snippets))
    if any(token in text.lower() for token in ("deadline", "締切")):
        return text[:120]
    return ""


def _warn(shaped: dict[str, Any], message: str) -> None:
    if message not in shaped["warnings"]:
        shaped["warnings"].append(message)


def _invalid_faculty_department_pair(faculty: str, department: str) -> bool:
    faculty = _clean_text(faculty)
    department = _clean_text(department)
    if not faculty:
        return True
    if faculty == "学部一括":
        return True
    if department and "学部" in department and department not in {"学部一括", "学科一括"}:
        if faculty not in department:
            return True
        if "・" in department or "／" in department or "/" in department:
            return True
    return False


def _strip_english_from_eju_fields(shaped: dict[str, Any]) -> None:
    for field in EJU_SUBJECT_LABELS:
        value = shaped.get(field, "")
        if value and any(marker in value for marker in ENGLISH_TEST_MARKERS):
            shaped[field] = ""
            shaped["field_evidence"][field] = {"text": "", "page": None}
            _warn(shaped, f"{field} cleared because it looked like an English test requirement")


def _strip_eju_subjects_from_english(shaped: dict[str, Any]) -> None:
    value = shaped.get("english_requirement", "")
    if not value:
        return
    if any(marker in value for marker in ENGLISH_TEST_MARKERS):
        return
    if any(token in value for labels in EJU_SUBJECT_LABELS.values() for token in labels):
        shaped["english_requirement"] = ""
        shaped["field_evidence"]["english_requirement"] = {"text": "", "page": None}
        _warn(shaped, "english_requirement cleared because it looked like EJU subject content")


CONDITIONAL_SYMBOL_RE = re.compile(r"[△▲※注＊*]")
POSITIVE_SYMBOL_RE = re.compile(r"[○◯◎●]|必須|必要|要|提出|可")
NEGATIVE_SYMBOL_RE = re.compile(r"^(?:[-－ー―—]+|×|不要|なし|無し|該当なし|空欄)?$")


def _record_key_text(value: Any) -> str:
    text = _clean_text(value)
    return re.sub(r"[\s　・･/／、,，\-－―ー]+", "", text)


def _symbol_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        return " ".join(_clean_text(item) for item in value if _clean_text(item))
    return _clean_text(value)


def _symbol_cell_is_active(value: Any) -> bool:
    text = _symbol_text(value)
    if not text:
        return False
    if NEGATIVE_SYMBOL_RE.fullmatch(text):
        return False
    return bool(POSITIVE_SYMBOL_RE.search(text))


def _symbol_cell_is_conditional(value: Any) -> bool:
    return bool(CONDITIONAL_SYMBOL_RE.search(_symbol_text(value)))


def _symbol_has_note(row: dict[str, Any]) -> bool:
    if any(_clean_text(note) for note in row.get("notes") or []):
        return True
    symbols = row.get("symbols") if isinstance(row.get("symbols"), dict) else {}
    return any(_symbol_cell_is_conditional(value) for value in symbols.values())


def _evidence_from_symbol_row(row: dict[str, Any], field: str, symbol_label: str = "") -> dict[str, Any]:
    page = row.get("page")
    try:
        page = int(page) if page not in ("", None) else None
    except Exception:
        page = None
    notes = [str(note).strip() for note in (row.get("notes") or []) if str(note).strip()]
    evidence = _clean_text(row.get("evidence_text"))
    if symbol_label:
        evidence = f"{symbol_label}: {evidence}".strip(": ")
    if notes:
        evidence = f"{evidence} Notes: {' / '.join(notes)}".strip()
    return {"text": evidence[:260] if evidence else symbol_label, "page": page}


def _append_patch_warning(record: dict[str, Any], message: str) -> None:
    warnings = list(record.get("warnings") or record.get("warnings_json") or [])
    if message not in warnings:
        warnings.append(message)
    record["warnings"] = warnings
    record["warnings_json"] = warnings


def _set_patch_field(record: dict[str, Any], field: str, value: str, row: dict[str, Any], symbol_label: str) -> None:
    if not value:
        return
    record[field] = value
    evidence = dict(record.get("field_evidence") or {}) if isinstance(record.get("field_evidence"), dict) else {}
    confidence = dict(record.get("field_confidence") or {}) if isinstance(record.get("field_confidence"), dict) else {}
    evidence[field] = _evidence_from_symbol_row(row, field, symbol_label)
    confidence[field] = 0.72 if _symbol_has_note(row) else 0.86
    record["field_evidence"] = evidence
    record["field_confidence"] = confidence
    record["needs_review"] = True if _symbol_has_note(row) else record.get("needs_review", True)
    if _symbol_has_note(row):
        _append_patch_warning(record, f"{field} has conditional table symbol; verify table note")


def _english_label_for_column(column: str) -> str:
    source = column.upper()
    if "TOEFL" in source and "IBT" in source:
        return "TOEFL iBT"
    if "TOEFL" in source:
        return "TOEFL"
    if "IELTS" in source:
        return "IELTS Academic Module" if "ACADEMIC" in source or "アカデミック" in column else "IELTS"
    if "TOEIC" in source and ("L&R" in source or "LISTENING" in source or "READING" in source):
        return "TOEIC L&R"
    if "TOEIC" in source:
        return "TOEIC"
    if "ドイツ" in column:
        return "ドイツ語"
    if "フランス" in column:
        return "フランス語"
    return ""


def _screening_label_for_column(column: str) -> str:
    if "書類" in column:
        return "書類選考"
    if "小論文" in column:
        return "小論文"
    if "学力" in column or "筆記" in column or "試験" in column:
        return "学力試験"
    if "面接" in column or "面談" in column:
        return "面接"
    if "口頭" in column or "口述" in column:
        return "口頭試問"
    return ""


def _symbol_row_to_field_patch(row: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {
        "faculty": _clean_text(row.get("faculty")),
        "department": _normalize_department_value(_clean_text(row.get("department"))),
        "warnings": [],
        "field_evidence": {},
        "field_confidence": {},
    }
    symbols = row.get("symbols") if isinstance(row.get("symbols"), dict) else {}
    english_labels: list[str] = []
    screening_labels: list[str] = []
    math_courses: set[str] = set()

    for raw_column, raw_symbol in symbols.items():
        column = _clean_text(raw_column)
        symbol = _symbol_text(raw_symbol)
        if not column:
            continue
        if _symbol_cell_is_conditional(symbol):
            _append_patch_warning(patch, f"conditional table symbol preserved: {column}={symbol}")
        if not _symbol_cell_is_active(symbol):
            continue

        conditional_label = f"{column}={symbol}" if _symbol_cell_is_conditional(symbol) else column
        if "日本語" in column and "英語" not in column:
            _set_patch_field(patch, "eju_japanese", "日本語", row, conditional_label)
        elif "総合科目" in column or "综合科目" in column:
            _set_patch_field(patch, "eju_general", "総合科目", row, conditional_label)
        elif "数学" in column:
            if re.search(r"(コース\s*1|コース1|course\s*1)", column, re.IGNORECASE):
                math_courses.add("1")
            elif re.search(r"(コース\s*2|コース2|course\s*2)", column, re.IGNORECASE):
                math_courses.add("2")
            else:
                math_courses.add("")
        elif "物理" in column:
            _set_patch_field(patch, "eju_physics", "物理", row, conditional_label)
        elif "化学" in column:
            _set_patch_field(patch, "eju_chemistry", "化学", row, conditional_label)
        elif "生物" in column:
            _set_patch_field(patch, "eju_biology", "生物", row, conditional_label)

        english_label = _english_label_for_column(column)
        if english_label and english_label not in english_labels:
            english_labels.append(english_label)

        screening_label = _screening_label_for_column(column)
        if screening_label and screening_label not in screening_labels:
            screening_labels.append(screening_label)

    if math_courses:
        if {"1", "2"} <= math_courses or "" in math_courses and ({"1", "2"} & math_courses):
            math_value = "数学(コース1または2)"
        elif "1" in math_courses:
            math_value = "数学(コース1)"
        elif "2" in math_courses:
            math_value = "数学(コース2)"
        else:
            math_value = "数学"
        _set_patch_field(patch, "eju_math", math_value, row, "数学")

    if english_labels:
        _set_patch_field(patch, "english_requirement", " / ".join(english_labels), row, "英語外部資格試験")
    if screening_labels:
        _set_patch_field(patch, "screening_method", " / ".join(screening_labels), row, "選考方法")

    notes = [str(note).strip() for note in (row.get("notes") or []) if str(note).strip()]
    for note in notes:
        _append_patch_warning(patch, f"table note: {note[:160]}")
    return patch


def _department_looks_invented(faculty: str, department: str) -> bool:
    faculty_clean = _clean_text(faculty)
    department_clean = _clean_text(department)
    if not faculty_clean or not department_clean:
        return False
    if faculty_clean.endswith("学部") and department_clean == faculty_clean[:-2] + "学科":
        return True
    if faculty_clean.endswith("理工学部") and department_clean.endswith("理工学科"):
        return True
    return False


def _field_patch_is_more_specific(field: str, current: str, incoming: str) -> bool:
    current = _clean_text(current)
    incoming = _clean_text(incoming)
    if not incoming:
        return False
    if not current:
        return True
    if current == incoming:
        return False
    if field == "eju_math":
        return "コース" in incoming and (incoming != current)
    if field == "english_requirement":
        generic = current in {"TOEFL / IELTS", "TOEFL / IELTS Academic Module", "TOEFL / IELTS / TOEIC"}
        return generic or len(incoming) > len(current) or len(incoming.split(" / ")) < len(current.split(" / "))
    if field == "screening_method":
        return current in {"学力試験 / 面接", "面接", "学力試験"} or len(incoming) > len(current)
    if field.startswith("eju_"):
        return True
    return False


def _merge_symbol_patch_into_record(record: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(record)
    if _department_looks_invented(merged.get("faculty", ""), merged.get("department", "")):
        if _clean_text(patch.get("department")):
            merged["department"] = patch["department"]
    elif not _clean_text(merged.get("department")) and _clean_text(patch.get("department")):
        merged["department"] = patch["department"]

    for field in [
        "eju_japanese",
        "eju_general",
        "eju_math",
        "eju_physics",
        "eju_chemistry",
        "eju_biology",
        "english_requirement",
        "screening_method",
    ]:
        if _field_patch_is_more_specific(field, merged.get(field, ""), patch.get(field, "")):
            merged[field] = patch[field]

    evidence = dict(merged.get("field_evidence") or {}) if isinstance(merged.get("field_evidence"), dict) else {}
    confidence = dict(merged.get("field_confidence") or {}) if isinstance(merged.get("field_confidence"), dict) else {}
    for field, item in (patch.get("field_evidence") or {}).items():
        if field in EVIDENCE_FIELDS and _clean_text(patch.get(field)):
            evidence[field] = item
    for field, score in (patch.get("field_confidence") or {}).items():
        if field in EVIDENCE_FIELDS and _clean_text(patch.get(field)):
            confidence[field] = score
    merged["field_evidence"] = evidence
    merged["field_confidence"] = confidence

    for warning in list(patch.get("warnings") or patch.get("warnings_json") or []):
        _append_patch_warning(merged, str(warning))
    if patch.get("needs_review"):
        merged["needs_review"] = True
    return merged


def _find_symbol_match(records: list[dict[str, Any]], patch: dict[str, Any], claimed: set[int]) -> int | None:
    patch_faculty = _record_key_text(patch.get("faculty"))
    patch_department = _record_key_text(patch.get("department"))
    if not patch_faculty:
        return None
    exact_department_match: int | None = None
    related_unclaimed_match: int | None = None
    faculty_only_match: int | None = None

    for idx, record in enumerate(records):
        faculty = _record_key_text(record.get("faculty"))
        department = _record_key_text(record.get("department"))
        if faculty != patch_faculty:
            continue
        if patch_department and department == patch_department:
            exact_department_match = idx
            break
        if idx not in claimed and _departments_related(_clean_text(record.get("department")), _clean_text(patch.get("department"))):
            related_unclaimed_match = idx
        if idx not in claimed and faculty_only_match is None:
            faculty_only_match = idx

    if exact_department_match is not None:
        return exact_department_match
    if related_unclaimed_match is not None:
        return related_unclaimed_match
    return faculty_only_match


def _apply_symbol_rows_to_records(records: list[dict[str, Any]], symbol_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not symbol_rows:
        return records
    patched_records = [dict(record) for record in records]
    claimed: set[int] = set()
    for row in symbol_rows:
        patch = _symbol_row_to_field_patch(row)
        if not _clean_text(patch.get("faculty")):
            continue
        if _department_looks_invented(patch.get("faculty", ""), patch.get("department", "")):
            continue
        idx = _find_symbol_match(patched_records, patch, claimed)
        if idx is None:
            patched_records.append(patch)
            claimed.add(len(patched_records) - 1)
            continue
        patched_records[idx] = _merge_symbol_patch_into_record(patched_records[idx], patch)
        claimed.add(idx)
    return patched_records


def _record_identity(record: dict[str, Any]) -> tuple[str, str]:
    return (_clean_text(record.get("faculty")), _clean_text(record.get("department")))


def _department_tokens(value: str) -> list[str]:
    raw = _clean_text(value)
    if not raw:
        return []
    parts = re.split(r"[、,，/／]\s*", raw)
    return [part.strip() for part in parts if part.strip()]


def _departments_related(base_department: str, incoming_department: str) -> bool:
    if not base_department or not incoming_department:
        return not base_department or not incoming_department
    if base_department == incoming_department:
        return True
    if base_department in incoming_department or incoming_department in base_department:
        return True
    base_tokens = _department_tokens(base_department)
    incoming_tokens = _department_tokens(incoming_department)
    return bool(base_tokens and incoming_tokens and set(base_tokens) & set(incoming_tokens))


def _requirement_signature(record: dict[str, Any]) -> tuple[str, ...]:
    return tuple(_clean_text(record.get(field)) for field in REQUIREMENT_FIELDS)


def _records_are_compatible(base_record: dict[str, Any], incoming_record: dict[str, Any]) -> bool:
    for field in REQUIREMENT_FIELDS:
        base_value = _clean_text(base_record.get(field))
        incoming_value = _clean_text(incoming_record.get(field))
        if base_value and incoming_value and base_value != incoming_value:
            return False
    return True


def _merge_field_evidence(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = _empty_evidence()
    for field in EVIDENCE_FIELDS:
        base_item = (base or {}).get(field) or {}
        incoming_item = (incoming or {}).get(field) or {}
        merged[field] = base_item if base_item.get("text") else incoming_item
        if not merged[field]:
            merged[field] = {"text": "", "page": None}
    return merged


def _merge_record_pair(
    base_output: dict[str, Any],
    base_staging: dict[str, Any],
    incoming_output: dict[str, Any],
    incoming_staging: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    merged_output = dict(base_output)
    merged_staging = dict(base_staging)
    if len(_clean_text(incoming_output.get("department"))) > len(_clean_text(merged_output.get("department"))):
        merged_output["department"] = incoming_output.get("department", "")
        merged_staging["department"] = incoming_staging.get("department", "")
    for field in RECORD_FIELDS:
        if field in {"warnings", "field_evidence", "confidence", "needs_review"}:
            continue
        if not _clean_text(merged_output.get(field)) and _clean_text(incoming_output.get(field)):
            merged_output[field] = incoming_output.get(field, "")
        if not _clean_text(merged_staging.get(field)) and _clean_text(incoming_staging.get(field)):
            merged_staging[field] = incoming_staging.get(field, "")
    merged_output["warnings"] = list(
        dict.fromkeys(list(base_output.get("warnings") or []) + list(incoming_output.get("warnings") or []))
    )
    merged_staging["warnings_json"] = list(
        dict.fromkeys(list(base_staging.get("warnings_json") or []) + list(incoming_staging.get("warnings_json") or []))
    )
    merged_output["field_evidence"] = _merge_field_evidence(
        base_output.get("field_evidence") or {},
        incoming_output.get("field_evidence") or {},
    )
    merged_staging["field_evidence"] = _merge_field_evidence(
        base_staging.get("field_evidence") or {},
        incoming_staging.get("field_evidence") or {},
    )
    merged_output["confidence"] = round(
        max(float(base_output.get("confidence") or 0.0), float(incoming_output.get("confidence") or 0.0)),
        4,
    )
    merged_staging["confidence"] = merged_output["confidence"]
    merged_output["needs_review"] = bool(base_output.get("needs_review")) or bool(incoming_output.get("needs_review"))
    merged_staging["needs_review"] = int(merged_output["needs_review"])
    if incoming_staging.get("raw_llm_json") and len(str(incoming_staging["raw_llm_json"])) > len(str(base_staging.get("raw_llm_json") or "")):
        merged_staging["raw_llm_json"] = incoming_staging["raw_llm_json"]
    return merged_output, merged_staging


def _dedupe_record_pairs(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    merged: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for output_record, staging_record in pairs:
        identity = _record_identity(output_record)
        if not any(identity):
            merged.append((output_record, staging_record))
            continue
        merged_into_existing = False
        for idx, (existing_output, existing_staging) in enumerate(merged):
            existing_faculty, existing_department = _record_identity(existing_output)
            faculty, department = identity
            if existing_faculty != faculty:
                continue
            if not _departments_related(existing_department, department):
                continue
            if not _records_are_compatible(existing_output, output_record):
                continue
            merged[idx] = _merge_record_pair(existing_output, existing_staging, output_record, staging_record)
            merged_into_existing = True
            break
        if not merged_into_existing:
            merged.append((output_record, staging_record))
    return merged


def _sanitize_record(
    record: dict[str, Any],
    top_level: dict[str, Any],
    page_texts: dict[int, str],
    raw_result: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    shaped = _exact_record_shape()
    for field in RECORD_FIELDS:
        if field == "confidence":
            try:
                shaped[field] = round(float(record.get(field, 0.0) or 0.0), 4)
            except Exception:
                shaped[field] = 0.0
            continue
        if field == "needs_review":
            shaped[field] = bool(record.get(field, True))
            continue
        if field == "warnings":
            warnings = record.get("warnings") or record.get("warnings_json") or []
            if isinstance(warnings, list):
                shaped[field] = [str(item).strip() for item in warnings if str(item).strip()]
            continue
        if field == "field_evidence":
            evidence = normalize_field_evidence(record.get("field_evidence"))
            merged = _empty_evidence()
            for evidence_field in EVIDENCE_FIELDS:
                if evidence_field in evidence:
                    merged[evidence_field] = evidence[evidence_field]
            shaped[field] = merged
            continue
        shaped[field] = _clean_text(record.get(field))

    shaped["department"] = _normalize_department_value(shaped["department"])
    shaped["faculty"] = _normalize_list_delimiters(shaped["faculty"])

    if not shaped["application_period"]:
        shaped["application_period"] = top_level.get("application_period", "")
    if not shaped["deadline_rule"]:
        shaped["deadline_rule"] = top_level.get("deadline_rule", "")
    shaped["deadline_rule"] = _normalize_deadline_rule(shaped["deadline_rule"]) or shaped["deadline_rule"]

    for evidence_field in EVIDENCE_FIELDS:
        if not shaped["field_evidence"][evidence_field]["text"]:
            shaped["field_evidence"][evidence_field] = _find_field_evidence(
                evidence_field,
                shaped.get(evidence_field, ""),
                page_texts,
            )

    if shaped["deadline_rule"]:
        shaped["field_evidence"]["deadline_rule"] = _find_field_evidence(
            "deadline_rule",
            shaped["deadline_rule"],
            page_texts,
        )

    _strip_english_from_eju_fields(shaped)
    _strip_eju_subjects_from_english(shaped)
    if _invalid_faculty_department_pair(shaped["faculty"], shaped["department"]):
        _warn(shaped, "faculty/department pairing looks invalid")
        shaped["needs_review"] = True

    staging_record = {
        "university": top_level.get("university", ""),
        "admission_year": top_level.get("admission_year", ""),
        "admission_period": "",
        "faculty": shaped["faculty"],
        "department": shaped["department"],
        "application_period": shaped["application_period"],
        "deadline_rule": shaped["deadline_rule"],
        "japanese_exam": shaped["japanese_exam"],
        "eju_session": shaped["eju_session"],
        "eju_japanese": shaped["eju_japanese"],
        "eju_general": shaped["eju_general"],
        "eju_math": shaped["eju_math"],
        "eju_physics": shaped["eju_physics"],
        "eju_chemistry": shaped["eju_chemistry"],
        "eju_biology": shaped["eju_biology"],
        "english_requirement": shaped["english_requirement"],
        "screening_method": shaped["screening_method"],
        "screening_schedule": shaped["screening_schedule"],
        "result_date": shaped["result_date"],
        "enrollment_period": shaped["enrollment_period"],
        "prefecture": shaped["prefecture"],
        "campus": shaped["campus"],
        "confidence": shaped["confidence"],
        "needs_review": int(shaped["needs_review"]),
        "warnings_json": list(shaped["warnings"]),
        "field_evidence": shaped["field_evidence"],
        "manual_modified_fields": [],
        "raw_llm_json": raw_result.get("_raw_response", ""),
    }
    validated = validate(staging_record)
    shaped["confidence"] = round(float(validated.get("confidence") or 0.0), 4)
    shaped["needs_review"] = bool(validated.get("needs_review"))
    shaped["warnings"] = list(validated.get("warnings_json") or [])
    shaped["field_evidence"] = normalize_field_evidence(validated.get("field_evidence"))
    return shaped, validated


def _default_top_level() -> dict[str, Any]:
    return {
        "university": "",
        "admission_year": "",
        "admission_system": "",
        "application_period": "",
        "deadline_rule": "",
        "records": [],
    }


def _nearby_page_context(page_texts: dict[int, str], page_num: int | None, radius: int = 1) -> str:
    if page_num is None:
        return ""
    sections: list[str] = []
    for page in range(max(1, page_num - radius), page_num + radius + 1):
        text = page_texts.get(page, "")
        if text.strip():
            sections.append(f"=== PAGE {page} TEXT ===\n{text}")
    return "\n\n".join(sections)[:24000]


def _extract_symbol_rows(
    pdf_path: Path,
    table_pages: list[int],
    page_texts: dict[int, str],
    *,
    vision_model: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    if not table_pages:
        return []
    image_dir = ROOT / "output_pages" / f"extract_fields_symbol_rows_{pdf_path.stem}"
    rendered = _render_candidate_images(pdf_path, image_dir, table_pages)
    symbol_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, str, int | None, str]] = set()

    for image_path in rendered:
        page_match = re.search(r"page_(\d+)\.png", image_path.name)
        page_num = int(page_match.group(1)) if page_match else None
        nearby_text = _nearby_page_context(page_texts, page_num)
        for variant_name, variant_paths in _table_image_variants(image_path, image_dir):
            user_content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        f"PDF file: {pdf_path.name}\n"
                        f"Page: {page_num}\n"
                        f"View: {variant_name}\n\n"
                        "Image order:\n"
                        "1. Full page image: primary evidence for headers, symbols, notes, and footnotes.\n"
                        "2. Row-band crop if present: zoom support only.\n"
                        "3. Left/faculty anchor crop if present: row alignment support only.\n\n"
                        "Use the full page and nearby text to interpret △ / ※ / 注 / footnotes. "
                        "Never discard conditional symbols. Never rely on an isolated crop as the only evidence.\n\n"
                        f"[nearby_text]\n{nearby_text}"
                    ),
                }
            ]
            for path in variant_paths:
                user_content.append({"type": "image_url", "image_url": {"url": _image_data_url(path)}})
            messages = [
                {"role": "system", "content": SYMBOL_ABSTRACTION_PROMPT},
                {"role": "user", "content": user_content},
            ]
            try:
                result = _call_llm(
                    messages,
                    vision_model,
                    max_tokens=9000,
                    timeout_seconds=timeout_seconds,
                )
            except Exception:
                continue
            for row in result.get("symbol_rows") or []:
                if not isinstance(row, dict):
                    continue
                row = dict(row)
                if page_num is not None and row.get("page") in ("", None):
                    row["page"] = page_num
                faculty = _clean_text(row.get("faculty"))
                department = _normalize_department_value(_clean_text(row.get("department")))
                if not faculty:
                    continue
                row["faculty"] = faculty
                row["department"] = department
                symbols = row.get("symbols") if isinstance(row.get("symbols"), dict) else {}
                active_symbols = {
                    _clean_text(key): _symbol_text(value)
                    for key, value in symbols.items()
                    if _clean_text(key) and _symbol_text(value)
                }
                row["symbols"] = active_symbols
                signature = (
                    _record_key_text(faculty),
                    _record_key_text(department),
                    row.get("page"),
                    json.dumps(active_symbols, ensure_ascii=False, sort_keys=True),
                )
                if signature in seen:
                    continue
                seen.add(signature)
                symbol_rows.append(row)
    return symbol_rows


def _table_patch_records(
    pdf_path: Path,
    table_pages: list[int],
    *,
    vision_model: str,
    timeout_seconds: int,
) -> list[dict[str, Any]]:
    if not table_pages:
        return []
    image_dir = ROOT / "output_pages" / f"extract_fields_table_patch_{pdf_path.stem}"
    rendered = _render_candidate_images(pdf_path, image_dir, table_pages)
    patched: list[dict[str, Any]] = []
    for image_path in rendered:
        page_match = re.search(r"page_(\d+)\.png", image_path.name)
        page_num = int(page_match.group(1)) if page_match else None
        for variant_name, variant_paths in _table_image_variants(image_path, image_dir):
            user_content: list[dict[str, Any]] = [
                {
                    "type": "text",
                    "text": (
                        f"PDF file: {pdf_path.name}\n"
                        f"Page: {page_num}\n"
                        f"Crop: {variant_name}\n"
                        "Image 1 is the full page anchor.\n"
                        "Image 2 is the row-band focus crop.\n"
                        "Image 3 is the left/faculty-column anchor crop for row alignment.\n"
                        "Extract only the rows visible in the focus band, but use the full page and left anchor to preserve row context.\n"
                        "Preserve 学部一括 / 学科一括 when shown.\n"
                        "If one row lists multiple departments under one requirement set, keep them in one record.\n"
                        "Leave unclear fields empty instead of guessing."
                    ),
                }
            ]
            for path in variant_paths:
                user_content.append({"type": "image_url", "image_url": {"url": _image_data_url(path)}})
            messages = [
                {"role": "system", "content": TABLE_PATCH_PROMPT},
                {
                    "role": "user",
                    "content": user_content,
                },
            ]
            try:
                result = _call_llm(
                    messages,
                    vision_model,
                    max_tokens=7000,
                    timeout_seconds=timeout_seconds,
                )
            except Exception:
                continue
            for record in result.get("records") or []:
                if isinstance(record, dict):
                    patched.append(record)
    return patched


def extract_fields(
    pdf_path: Path,
    *,
    text_model: str,
    vision_model: str,
    use_images: bool,
    max_images: int,
    timeout_seconds: int,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    page_texts = extract_text_per_page(pdf_path)
    candidate_pages = _candidate_pages(page_texts, max(2, max_images))
    table_pages = _table_support_pages(page_texts, candidate_pages, 1)
    context_text = _build_text_context(page_texts, candidate_pages)

    content: list[dict[str, Any]] = [
        {
            "type": "text",
            "text": (
                f"[file_name]\n{pdf_path.name}\n\n"
                f"[instructions]\nUse this PDF as a Japanese admissions guideline (募集要項). "
                "Extract the fixed fields only. Enumerate all faculty/department rows within scope. "
                "Keep faculty rows separate when requirements differ. Preserve 学部一括 / 学科一括 when shown. "
                "If one row lists multiple departments under a shared requirement set, keep them in one record. "
                "If a field is unclear, leave it empty and add a warning.\n\n"
                f"[candidate_pages]\n{candidate_pages}\n\n"
                f"[table_support_pages]\n{table_pages}\n\n"
                f"[pdf_text]\n{context_text}"
            ),
        }
    ]

    image_paths: list[Path] = []
    if use_images and candidate_pages:
        image_dir = ROOT / "output_pages" / f"extract_fields_{pdf_path.stem}"
        image_paths = _render_candidate_images(pdf_path, image_dir, candidate_pages[:max_images])
        for image_path in image_paths[:max_images]:
            content.append({"type": "image_url", "image_url": {"url": _image_data_url(image_path)}})

    messages = [
        {"role": "system", "content": _load_prompt()},
        {"role": "user", "content": content},
    ]
    raw_result = _call_llm(messages, text_model if not image_paths else vision_model, timeout_seconds=timeout_seconds)
    base_records = [item for item in (raw_result.get("records") or []) if isinstance(item, dict)]
    if use_images and image_paths and len(base_records) < 10:
        text_only_messages = [
            {"role": "system", "content": _load_prompt()},
            {"role": "user", "content": content[:1]},
        ]
        try:
            text_only_result = _call_llm(
                text_only_messages,
                text_model,
                timeout_seconds=timeout_seconds,
            )
            text_only_records = [item for item in (text_only_result.get("records") or []) if isinstance(item, dict)]
            if len(text_only_records) > len(base_records):
                raw_result = text_only_result
                base_records = text_only_records
        except Exception:
            pass

    patch_records: list[dict[str, Any]] = []
    symbol_rows: list[dict[str, Any]] = []
    if use_images and table_pages:
        symbol_rows = _extract_symbol_rows(
            pdf_path,
            table_pages,
            page_texts,
            vision_model=vision_model,
            timeout_seconds=timeout_seconds,
        )
        if symbol_rows:
            base_records = _apply_symbol_rows_to_records(base_records, symbol_rows)
    sparse_base = any(
        not _clean_text(item.get(field))
        for item in base_records
        for field in ("english_requirement", "screening_method", "eju_japanese", "eju_general", "eju_math")
    )
    if use_images and table_pages and sparse_base and not symbol_rows:
        patch_records = _table_patch_records(
            pdf_path,
            table_pages,
            vision_model=vision_model,
            timeout_seconds=timeout_seconds,
        )

    top_level = _default_top_level()
    for field in TOP_LEVEL_FIELDS:
        top_level[field] = _clean_text(raw_result.get(field))

    if not top_level["university"]:
        top_level["university"] = _fallback_university(page_texts, pdf_path)
    else:
        top_level["university"] = _clean_university(top_level["university"])
    if not top_level["admission_year"]:
        top_level["admission_year"] = _fallback_year(page_texts)
    if not top_level["admission_system"]:
        top_level["admission_system"] = _fallback_system(page_texts)
    if not top_level["application_period"]:
        top_level["application_period"] = _fallback_application_period(page_texts)
    if not top_level["deadline_rule"]:
        top_level["deadline_rule"] = _fallback_deadline_rule(page_texts)
    top_level["deadline_rule"] = _normalize_deadline_rule(top_level["deadline_rule"]) or top_level["deadline_rule"]

    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for item in base_records + patch_records:
        if not isinstance(item, dict):
            continue
        output_record, staging_record = _sanitize_record(item, top_level, page_texts, raw_result)
        if _invalid_faculty_department_pair(output_record.get("faculty", ""), output_record.get("department", "")):
            continue
        pairs.append((output_record, staging_record))

    merged_pairs = _dedupe_record_pairs(pairs)
    output_records = [item[0] for item in merged_pairs]
    staging_records = [item[1] for item in merged_pairs]
    top_level["records"] = output_records
    return top_level, staging_records


def save_to_staging(
    output: dict[str, Any],
    staging_records: list[dict[str, Any]],
    pdf_path: Path,
    *,
    source_url: str = "",
) -> dict[str, Any]:
    init_db()
    doc_id = create_source_document(
        university=output.get("university", "") or "待识别",
        file_name=pdf_path.name,
        file_path=str(pdf_path),
        pdf_url=source_url,
        admission_year=output.get("admission_year", ""),
    )
    inserted = 0
    for record in staging_records:
        page_number = None
        for field in EVIDENCE_FIELDS:
            page = record.get("field_evidence", {}).get(field, {}).get("page")
            if page:
                page_number = int(page)
                break
        insert_staging_record(doc_id, page_number, record)
        inserted += 1
    update_source_document(
        doc_id,
        status="extract_fields_completed",
        university=output.get("university", ""),
        admission_year=output.get("admission_year", ""),
    )
    duplicate_cleanup = prune_duplicate_documents(doc_id)
    return {
        "doc_id": doc_id,
        "inserted": inserted,
        "duplicate_cleanup": duplicate_cleanup,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract fixed admissions fields from a Japanese 募集要項 PDF.")
    parser.add_argument("pdf_path", type=Path, help="Path to the admissions PDF.")
    parser.add_argument("--output", type=Path, required=True, help="Path to save extracted JSON.")
    parser.add_argument("--text-model", default=_load_env_value("OPENAI_TEXT_MODEL", DEFAULT_TEXT_MODEL))
    parser.add_argument("--vision-model", default=_load_env_value("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL))
    parser.add_argument("--timeout-seconds", type=int, default=180)
    parser.add_argument("--max-images", type=int, default=4)
    parser.add_argument("--no-images", action="store_true", help="Disable page-image rendering and run text-only extraction.")
    parser.add_argument("--save-staging", action="store_true", help="Also save extracted records into the staging database.")
    parser.add_argument("--source-url", default="", help="Optional source URL to store when saving to staging.")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.pdf_path.exists():
        print(f"PDF not found: {args.pdf_path}", file=sys.stderr)
        return 2

    result, staging_records = extract_fields(
        args.pdf_path,
        text_model=args.text_model,
        vision_model=args.vision_model,
        use_images=not args.no_images,
        max_images=max(1, args.max_images),
        timeout_seconds=max(30, args.timeout_seconds),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    summary: dict[str, Any] = {
        "output": str(args.output),
        "records": len(result.get("records") or []),
        "university": result.get("university", ""),
        "admission_year": result.get("admission_year", ""),
    }
    if args.save_staging:
        summary["staging"] = save_to_staging(result, staging_records, args.pdf_path, source_url=args.source_url)

    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
