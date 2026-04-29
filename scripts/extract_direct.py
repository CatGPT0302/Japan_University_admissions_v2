from __future__ import annotations

import argparse
import base64
import collections
import json
import os
import re
import sys
import time
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
from scripts.validator import CRITICAL_FIELDS, validate  # noqa: E402

PROMPT_PATH = ROOT / "prompts" / "vision_prompt.md"
DEFAULT_CHAT_COMPLETIONS_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TEXT_MODEL = "gpt-5.4-mini"
DEFAULT_VISION_MODEL = "gpt-4o-mini"
AUTO_UNIVERSITY_PLACEHOLDER = "待识别"
UNIVERSITY_PATTERN = re.compile(r"([一-龥ぁ-んァ-ヴーA-Za-z・･ー\-\s]{2,40}大学)")
UNIVERSITY_CONTEXT_KEYWORDS = (
    "外国人留学生",
    "留学生",
    "募集要項",
    "学生募集要項",
    "入学試験",
    "私費外国人留学生",
)
MEIJI_REQUIRED_FACULTIES = [
    "法学部",
    "商学部",
    "政治経済学部",
    "文学部",
    "理工学部",
    "農学部",
    "経営学部",
    "情報コミュニケーション学部",
    "国際日本学部",
    "総合数理学部",
]
WASEDA_REQUIRED_FACULTIES = [
    "政治経済学部",
    "法学部",
    "教育学部",
    "商学部",
    "社会科学部",
    "文化構想学部",
    "文学部",
    "基幹理工学部",
    "創造理工学部",
    "先進理工学部",
    "人間科学部",
    "スポーツ科学部",
]


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
                v = line.split("=", 1)[1].strip()
                if v:
                    return v
                break
    return default


def _load_first_env(names: list[str], default: str = "") -> str:
    for name in names:
        value = _load_env_value(name, "")
        if value:
            return value
    return default


def _load_api_key() -> str:
    key = _load_first_env(
        [
            "LLM_API_KEY",
            "OPENAI_API_KEY",
        ],
        "",
    )
    if not key:
        raise RuntimeError("API key not set (expected LLM_API_KEY or OPENAI_API_KEY)")
    return key


def _resolve_chat_completions_url() -> str:
    explicit = _load_first_env(
        [
            "OPENAI_COMPAT_URL",
            "LLM_COMPAT_URL",
            "OPENAI_URL",
        ],
        "",
    ).strip()
    if explicit:
        url = explicit.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"

    base = _load_first_env(
        [
            "OPENAI_BASE_URL",
            "LLM_BASE_URL",
        ],
        "",
    ).strip()
    if base:
        url = base.rstrip("/")
        if url.endswith("/chat/completions"):
            return url
        if url.endswith("/v1"):
            return url + "/chat/completions"
        return url + "/v1/chat/completions"

    return DEFAULT_CHAT_COMPLETIONS_URL


TEXT_MODEL = _load_env_value("OPENAI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
VISION_MODEL = _load_env_value("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)
EXTRACT_MAX_SECONDS = int(_load_env_value("EXTRACT_MAX_SECONDS", "0") or "0")
VISION_PATCH_MAX_PAGES = int(_load_env_value("VISION_PATCH_MAX_PAGES", "4") or "4")
VISION_PATCH_MAX_VARIANTS = int(_load_env_value("VISION_PATCH_MAX_VARIANTS", "2") or "2")
VISION_PATCH_MIN_RATIO = float(_load_env_value("VISION_PATCH_MIN_RATIO", "0.35") or "0.35")


def _remaining_seconds(deadline_ts: float | None) -> float | None:
    if not deadline_ts:
        return None
    return max(0.0, deadline_ts - time.monotonic())


def _ensure_time_budget(deadline_ts: float | None, stage: str) -> None:
    remaining = _remaining_seconds(deadline_ts)
    if remaining is not None and remaining <= 0:
        raise TimeoutError(f"time budget exceeded at {stage}")


def _request_timeout(deadline_ts: float | None, default_timeout: int = 240) -> int:
    remaining = _remaining_seconds(deadline_ts)
    if remaining is None:
        return default_timeout
    # Leave a small buffer for parsing / DB write.
    return max(20, min(default_timeout, int(max(1.0, remaining - 4.0))))


def _read_pdf_text(pdf_path: Path) -> tuple[str, dict[int, str]]:
    page_map = extract_text_per_page(pdf_path)
    texts = [f"=== PAGE {idx} ===\\n{text}" for idx, text in sorted(page_map.items()) if text]
    return "\\n\\n".join(texts), page_map


def _clean_university_name(value: str) -> str:
    raw = str(value or "").strip()
    match = re.search(r"([一-龥ぁ-んァ-ヴー・･ー\-\s]{2,40}大学)", raw)
    if match:
        raw = match.group(1)
    cleaned = re.sub(r"\s+", "", raw)
    cleaned = re.sub(r"^[A-Za-z0-9_\-]+(?=[一-龥ぁ-んァ-ヴー])", "", cleaned)
    if not cleaned.endswith("大学"):
        return ""
    if len(cleaned) < 3:
        return ""
    return cleaned


def _infer_university_with_llm(full_text: str, file_name: str, url: str = "") -> str:
    snippet = full_text[:18000]
    if not snippet.strip():
        return ""
    messages = [
        {
            "role": "system",
            "content": (
                "Identify the university name from the admissions guideline text. "
                "Return JSON only in the form {\"university\":\"...\"}. "
                "If unclear, return an empty string."
            ),
        },
        {
            "role": "user",
            "content": (
                f"[file_name]\\n{file_name}\\n\\n"
                f"[source_url]\\n{url or ''}\\n\\n"
                "[pdf_text]\\n"
                + snippet
            ),
        },
    ]
    try:
        result = _call_openai(messages, TEXT_MODEL, max_tokens=200, token_param="max_completion_tokens")
    except Exception:
        return ""
    return _clean_university_name(result.get("university") or "")


def _infer_university_from_pdf(pdf_path: Path, full_text: str, url: str = "") -> str:
    probe_text = "\\n".join(filter(None, [pdf_path.stem, url, full_text[:50000]]))
    scores: dict[str, int] = {}

    for match in UNIVERSITY_PATTERN.finditer(probe_text):
        name = _clean_university_name(match.group(1))
        if not name:
            continue
        score = 1
        context = probe_text[max(0, match.start() - 80): min(len(probe_text), match.end() + 80)]
        for keyword in UNIVERSITY_CONTEXT_KEYWORDS:
            if keyword in context:
                score += 3
        if name in pdf_path.stem:
            score += 8
        if url and name in url:
            score += 4
        scores[name] = scores.get(name, 0) + score

    if scores:
        ranked = sorted(scores.items(), key=lambda item: item[1], reverse=True)
        best_name, best_score = ranked[0]
        second_score = ranked[1][1] if len(ranked) > 1 else 0
        if best_score >= 6 and best_score - second_score >= 2:
            return best_name

    return _infer_university_with_llm(full_text, pdf_path.name, url)


def _pick_final_university(raw_result: dict[str, Any] | None, fallback: str) -> str:
    fallback = _clean_university_name(fallback)
    if fallback and fallback != AUTO_UNIVERSITY_PLACEHOLDER:
        return fallback
    if raw_result:
        top_level = _clean_university_name(str(raw_result.get("university") or ""))
        if top_level:
            return top_level
        for record in raw_result.get("records") or []:
            candidate = _clean_university_name(str(record.get("university") or ""))
            if candidate:
                return candidate
    return fallback or AUTO_UNIVERSITY_PLACEHOLDER


def _data_url_from_image(image_path: Path) -> str:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _call_openai(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 12000,
    token_param: str = "max_tokens",
    request_timeout: int = 240,
) -> dict[str, Any]:
    api_key = _load_api_key()
    api_url = _resolve_chat_completions_url()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        token_param: max_tokens,
    }
    req = urllib_request.Request(
        api_url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    last_error: Exception | None = None
    max_attempts = 1 if request_timeout <= 40 else 3
    for attempt in range(max_attempts):
        try:
            with urllib_request.urlopen(req, timeout=request_timeout) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < (max_attempts - 1):
                time.sleep(2.0 + attempt * 2.0)
                last_error = RuntimeError(f"LLM API error {e.code}: {body}")
                continue
            raise RuntimeError(f"LLM API error {e.code}: {body}") from e
        except Exception as e:
            last_error = e
            if attempt < (max_attempts - 1):
                time.sleep(1.5 + attempt)
                continue
            raise
    else:
        if last_error:
            raise last_error
        raise RuntimeError("LLM request failed")

    choice = raw["choices"][0]
    text = choice["message"]["content"]
    usage = raw.get("usage", {})
    finish_reason = choice.get("finish_reason")
    print("=== LLM RAW RESPONSE ===")
    print(text)
    print("=== END ===")
    print(
        "[tokens] input="
        + str(usage.get("prompt_tokens", 0))
        + ", output="
        + str(usage.get("completion_tokens", 0))
        + ", total="
        + str(usage.get("total_tokens", 0))
    )
    print("[finish_reason] " + str(finish_reason))
    result = extract_json_payload(text)
    result["_raw_response"] = text
    result["_usage"] = usage
    result["_finish_reason"] = finish_reason
    return result


def _build_system_prompt() -> str:
    return _load_prompt()


FIELD_KEYWORDS: dict[str, list[str]] = {
    "application_period": ["出願期間", "出願受付", "願書受付", "受付期間"],
    "deadline_rule": ["必着", "消印有効", "締切", "出願締切"],
    "eju_session": ["EJU", "実施回", "第1回", "第2回"],
    "eju_japanese": ["日本語"],
    "eju_general": ["総合科目"],
    "eju_math": ["数学", "コース1", "コース2"],
    "eju_physics": ["物理"],
    "eju_chemistry": ["化学"],
    "eju_biology": ["生物"],
    "english_requirement": ["TOEFL", "IELTS", "TOEIC", "英語外部資格試験", "英語"],
    "screening_method": ["選考方法", "選抜方法", "審査方法"],
    "screening_schedule": ["試験日", "選考日", "面接日", "選考日程"],
    "result_date": ["合格発表", "結果通知", "発表日"],
    "enrollment_period": ["入学手続", "手続期間", "入学手続期間"],
}


EJU_FIELD_LABELS: dict[str, str] = {
    "eju_japanese": "日本語",
    "eju_general": "総合科目",
    "eju_math": "数学",
    "eju_physics": "物理",
    "eju_chemistry": "化学",
    "eju_biology": "生物",
}

SCIENCE_FIELDS = ["eju_physics", "eju_chemistry", "eju_biology"]
EJU_CHOICE_MARKERS = ("いずれか1科目", "いずれか１科目", "1科目を選択", "１科目を選択", "から1科目", "から１科目")
EJU_NOTE_RE = re.compile(r"([0-9０-９]{2,3}\s*点|免除|免し|一次選考|1次選考)")
ENGLISH_EXAM_PATTERNS: list[tuple[str, str]] = [
    (r"TOEFL\s*iBT", "TOEFL iBT"),
    (r"TOEFL", "TOEFL"),
    (r"IELTS(?:\s*Academic(?:\s*Module)?)?", "IELTS"),
    (r"TOEIC\s*(?:L&R|Listening\s*&\s*Reading)", "TOEIC L&R"),
    (r"TOEIC", "TOEIC"),
]
ENGLISH_NOTE_RE = re.compile(r"([0-9０-９]{1,3}(?:\.[0-9０-９]+)?\s*点以上|基準点なし|出願基準点なし|免除|換算|CEFR|相当)")
DATE_FRAGMENT_RE = re.compile(
    r"(?:(?:20\d{2})\s*年\s*)?\d{1,2}\s*月\s*\d{1,2}\s*日"
    r"(?:\s*[（(][^)）]{1,6}[)）])?"
    r"(?:\s*\d{1,2}(?::|時)\d{2}(?:分)?)?"
)
MONTH_PHASE_RE = re.compile(r"(20\d{2}\s*年\s*\d{1,2}\s*月\s*(?:上旬|中旬|下旬))")
EJU_SESSION_RE = re.compile(r"(20\d{2}\s*年度\s*第\s*[12１２]\s*回|20\d{2}\s*年\s*(?:\d{1,2}\s*月)?回|第\s*[12１２]\s*回)")
SCREENING_METHOD_LABELS: list[tuple[str, str]] = [
    ("書類選考", "書類選考"),
    ("小論文", "小論文"),
    ("校内単独試験", "校内単独試験"),
    ("学力試験", "学力試験"),
    ("面接", "面接"),
    ("口頭試問", "口頭試問"),
]
FULLWIDTH_ASCII_TRANS = str.maketrans("０１２３４５６７８９：／（）－　", "0123456789:/()- ")
NORMALIZED_DATE_TOKEN_RE = re.compile(r"20\d{2}/\d{2}/\d{2}(?:\s*\((?:上旬|中旬|下旬)\))?")
NORMALIZED_MONTH_PHASE_TOKEN_RE = re.compile(r"20\d{2}/\d{2}(?:\s*\((?:上旬|中旬|下旬)\))?")
NORMALIZED_EJU_SESSION_TOKEN_RE = re.compile(r"20\d{2}年度第[12]回|第[12]回|20\d{2}/\d{2}")
RESULT_DATE_KEYWORDS = ("合格発表", "結果通知", "発表")


def _extract_snippet(page_text: str, candidates: list[str]) -> str:
    lines = [line.strip() for line in page_text.splitlines() if line.strip()]
    for candidate in candidates:
        if not candidate:
            continue
        for idx, line in enumerate(lines):
            if candidate in line:
                snippet = line
                if idx + 1 < len(lines) and len(snippet) < 120:
                    snippet = f"{snippet} {lines[idx + 1]}"
                return snippet[:220]
    return ""


def _find_evidence(field: str, value: str, page_map: dict[int, str], preferred_page: int | None = None) -> dict[str, Any]:
    ordered_pages: list[tuple[int, str]] = []
    if preferred_page and preferred_page in page_map:
        ordered_pages.append((preferred_page, page_map[preferred_page]))
    ordered_pages.extend((page_num, text) for page_num, text in page_map.items() if page_num != preferred_page)

    keywords = list(dict.fromkeys(([value] if value else []) + FIELD_KEYWORDS.get(field, [])))
    for page_num, page_text in ordered_pages:
        snippet = _extract_snippet(page_text, keywords)
        if snippet:
            return {"text": snippet, "page": page_num}

    return {"text": value or "", "page": preferred_page}


def _strip_eju_prefix(text: str) -> str:
    cleaned = str(text or "").strip()
    cleaned = re.sub(r"^[①-⑳⓪○●◎◯□■◆◇△▽▼▲※＊*・]+", "", cleaned)
    cleaned = re.sub(r"^\(?[0-9０-９]+\)?[\.．、 ]*", "", cleaned)
    return cleaned.strip()


def _symbol_to_eju_value(field: str, value: str) -> str:
    source = str(value or "").strip()
    if not source:
        return ""
    if re.fullmatch(r"[○●◎◯▲△\s]+", source):
        return EJU_FIELD_LABELS.get(field, source)
    if re.fullmatch(r"[□■▽▼※＊*・\s]+", source):
        return ""
    if source in {"必須", "必要", "要", "提出必須", "受験必須"}:
        return EJU_FIELD_LABELS.get(field, source)
    return source


def _extract_math_requirement(text: str) -> str:
    source = str(text or "")
    if "数学" not in source:
        return ""
    if re.search(r"コース\s*[12１２].*コース\s*[12１２]", source):
        return "数学(コース1または2)"
    if re.search(r"コース\s*[2２]", source):
        return "数学(コース2)"
    if re.search(r"コース\s*[1１]", source):
        return "数学(コース1)"
    return "数学"


def _normalize_eju_subject_value(field: str, value: str) -> str:
    source = str(value or "").strip()
    if not source:
        return ""
    label = EJU_FIELD_LABELS.get(field, "")
    if field == "eju_japanese":
        return "日本語" if "日本語" in source else source
    if field == "eju_general":
        return "総合科目" if "総合科目" in source else source
    if field == "eju_math":
        if "数学" not in source:
            return source
        if re.search(r"コース\s*[12１２].*コース\s*[12１２]", source) or re.search(r"コース\s*[1１]\s*または\s*[2２]", source):
            return "数学(コース1または2)"
        if re.search(r"コース\s*[2２]", source):
            return "数学(コース2)"
        if re.search(r"コース\s*[1１]", source):
            return "数学(コース1)"
        return "数学"
    if field in {"eju_physics", "eju_chemistry", "eju_biology"} and label and label in source:
        return label
    return source


def _append_record_note(record: dict[str, Any], note: str) -> None:
    if not note:
        return
    existing = list(record.get("warnings") or record.get("warnings_json") or [])
    prefix = note.split(":", 1)[0].strip()
    for item in existing:
        if str(item).split(":", 1)[0].strip() == prefix:
            deduped = list(dict.fromkeys(str(v).strip() for v in existing if str(v).strip()))
            record["warnings"] = deduped
            record["warnings_json"] = deduped
            return
    existing.append(note)
    deduped = list(dict.fromkeys(str(item).strip() for item in existing if str(item).strip()))
    record["warnings"] = deduped
    record["warnings_json"] = deduped


def _remove_record_notes(record: dict[str, Any], prefixes: list[str]) -> None:
    if not prefixes:
        return
    existing = list(record.get("warnings") or record.get("warnings_json") or [])
    if not existing:
        return
    kept = []
    for item in existing:
        text = str(item).strip()
        if not text:
            continue
        if any(text.startswith(prefix) for prefix in prefixes):
            continue
        kept.append(text)
    deduped = list(dict.fromkeys(kept))
    record["warnings"] = deduped
    record["warnings_json"] = deduped


def _is_placeholder_record(record: dict[str, Any]) -> bool:
    # Guardrail for quota/interruption artifacts that return shell rows only.
    key_fields = [
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
    ]
    if any(str(record.get(field) or "").strip() for field in key_fields):
        return False
    conf = 0.0
    try:
        conf = float(record.get("confidence") or 0.0)
    except Exception:
        conf = 0.0
    warnings = " ".join(str(w) for w in (record.get("warnings") or []))
    return conf <= 0.05 or ("Missing critical fields" in warnings)


def _extract_english_labels(text: str) -> list[str]:
    source = str(text or "")
    labels: list[str] = []
    for pattern, label in ENGLISH_EXAM_PATTERNS:
        if re.search(pattern, source, flags=re.IGNORECASE) and label not in labels:
            labels.append(label)
    if "TOEFL iBT" in labels and "TOEFL" in labels:
        labels.remove("TOEFL")
    if "TOEIC L&R" in labels and "TOEIC" in labels:
        labels.remove("TOEIC")
    return labels


def _normalize_application_period_value(value: str) -> str:
    source = str(value or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return ""
    existing_tokens = [match.group(0).strip() for match in NORMALIZED_DATE_TOKEN_RE.finditer(source)]
    existing_tokens = list(dict.fromkeys(token for token in existing_tokens if token))
    if existing_tokens:
        if any(marker in source for marker in ["~", "〜", "-"]) and len(existing_tokens) >= 2:
            return f"{existing_tokens[0]} - {existing_tokens[-1]}"
        if len(existing_tokens) == 1:
            return existing_tokens[0]
        return " / ".join(existing_tokens[:4])
    compact = re.sub(r"\s+", " ", source)
    compact = compact.replace("日本時間", "").replace("（日本時間）", "").replace("(日本時間)", "")
    compact = compact.replace("出願期間", "").replace("出願受付期間", "").replace("受付期間", "").replace("願書受付", "")
    parts = [match.group(0).strip() for match in DATE_FRAGMENT_RE.finditer(compact)]
    parts = list(dict.fromkeys(part for part in parts if part))
    if not parts:
        return compact.strip(" ：:／/、,")
    if any(marker in compact for marker in ["～", "~", "〜", "－", "-", "から"]) and len(parts) >= 2:
        return f"{parts[0]} ～ {parts[1]}"
    if len(parts) == 1:
        return parts[0]
    return " / ".join(parts[:4])


def _normalize_period_field_value(value: str) -> str:
    source = str(value or "").strip()
    if not source:
        return ""
    normalized = _normalize_application_period_value(source)
    if normalized:
        return normalized
    phases = list(dict.fromkeys(match.group(1).strip() for match in MONTH_PHASE_RE.finditer(source)))
    if phases:
        return " / ".join(phases[:4])
    cleaned = re.sub(r"(予定|ごろ|頃|まで|から)", " ", source)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:／/、,")
    return cleaned


def _format_date_fragment(text: str, fallback_year: int | None = None) -> tuple[str, int | None]:
    source = str(text or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return "", fallback_year
    year_match = re.search(r"(20\d{2})\s*年", source)
    month_match = re.search(r"(\d{1,2})\s*月", source)
    day_match = re.search(r"(\d{1,2})\s*日", source)
    if month_match and day_match:
        year = int(year_match.group(1)) if year_match else fallback_year
        if year:
            return f"{year:04d}/{int(month_match.group(1)):02d}/{int(day_match.group(1)):02d}", year
    phase_match = re.search(r"(20\d{2})\s*年\s*(\d{1,2})\s*月\s*(上旬|中旬|下旬)", source)
    if phase_match:
        return f"{int(phase_match.group(1)):04d}/{int(phase_match.group(2)):02d} ({phase_match.group(3)})", int(phase_match.group(1))
    return "", int(year_match.group(1)) if year_match else fallback_year


def _normalize_date_expression(value: str, mode: str = "list", strict_date_only: bool = False) -> str:
    source = str(value or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return ""

    normalized_tokens = [match.group(0).strip() for match in NORMALIZED_DATE_TOKEN_RE.finditer(source)]
    normalized_tokens = list(dict.fromkeys(token for token in normalized_tokens if token))

    if not normalized_tokens and not strict_date_only:
        normalized_tokens = [match.group(0).strip() for match in NORMALIZED_MONTH_PHASE_TOKEN_RE.finditer(source)]
        normalized_tokens = list(dict.fromkeys(token for token in normalized_tokens if token))

    if strict_date_only and normalized_tokens:
        normalized_tokens = [token for token in normalized_tokens if re.fullmatch(r"\d{4}/\d{2}/\d{2}", token)]

    if normalized_tokens:
        if mode == "range" and len(normalized_tokens) >= 2:
            return f"{normalized_tokens[0]} - {normalized_tokens[-1]}"
        if len(normalized_tokens) == 1:
            return normalized_tokens[0]
        return " / ".join(normalized_tokens[:6])

    fragments = [match.group(0).strip() for match in DATE_FRAGMENT_RE.finditer(source)]
    formatted: list[str] = []
    current_year: int | None = None
    for fragment in fragments:
        normalized, current_year = _format_date_fragment(fragment, current_year)
        if normalized and normalized not in formatted:
            formatted.append(normalized)

    if not strict_date_only:
        phases = list(dict.fromkeys(match.group(1).strip() for match in MONTH_PHASE_RE.finditer(source)))
        if phases:
            for phase in phases:
                normalized, current_year = _format_date_fragment(phase, current_year)
                if normalized and normalized not in formatted:
                    formatted.append(normalized)

    if not formatted:
        return ""

    dated = [item for item in formatted if re.match(r"\d{4}/\d{2}/\d{2}$", item)]
    phased = [item for item in formatted if item not in dated]
    dated = sorted(dated)
    formatted = dated if strict_date_only else (dated + phased)
    if not formatted:
        return ""
    if mode == "range" and len(formatted) >= 2:
        return f"{formatted[0]} - {formatted[-1]}"
    if len(formatted) == 1:
        return formatted[0]
    return " / ".join(formatted[:6])


def _collect_dates_from_segments(value: str, keep_result_segments: bool | None) -> str:
    source = str(value or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return ""
    parts = [part.strip() for part in re.split(r"[／/、,]+", source) if part.strip()]
    if len(parts) <= 1:
        return ""

    collected: list[str] = []
    for part in parts:
        has_result_keyword = any(keyword in part for keyword in RESULT_DATE_KEYWORDS)
        if keep_result_segments is True and not has_result_keyword:
            continue
        if keep_result_segments is False and has_result_keyword:
            continue
        normalized = _normalize_date_expression(part, mode="list")
        if not normalized:
            continue
        for token in [item.strip() for item in normalized.split(" / ") if item.strip()]:
            if token not in collected:
                collected.append(token)

    return " / ".join(collected[:6])


def _normalize_screening_schedule_value(value: str) -> str:
    source = str(value or "").strip()
    if not source:
        return ""
    filtered = _collect_dates_from_segments(source, keep_result_segments=False)
    if filtered:
        return filtered
    return _normalize_date_expression(source, mode="list")


def _normalize_result_date_value(value: str) -> str:
    source = str(value or "").strip()
    if not source:
        return ""
    filtered = _collect_dates_from_segments(source, keep_result_segments=True)
    if filtered:
        return filtered
    return _normalize_date_expression(source, mode="list")


def _normalize_eju_session_value(value: str) -> str:
    source = str(value or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return ""
    rounds: list[str] = []

    def add_round(label: str) -> None:
        if label not in rounds:
            rounds.append(label)

    # Direct pattern: 第1回 / 第2回
    for round_no in re.findall(r"第\s*([12１２])\s*回", source):
        n = round_no.translate(str.maketrans("１２", "12"))
        add_round("第一回" if n == "1" else "第二回")
    if "第一回" in source:
        add_round("第一回")
    if "第二回" in source:
        add_round("第二回")

    # Month-based fallback (EJU common sessions): 6月/7月 => 第一回, 11月 => 第二回
    for month_str in re.findall(r"(\d{1,2})\s*月(?:回)?", source):
        month = int(month_str)
        if month in {6, 7}:
            add_round("第一回")
        elif month == 11:
            add_round("第二回")

    # Date token fallback: infer month then map to first/second round.
    for token in re.findall(r"(20\d{2})/(\d{2})/\d{2}", _normalize_date_expression(source, mode="list", strict_date_only=True)):
        month = int(token[1])
        if month in {6, 7}:
            add_round("第一回")
        elif month == 11:
            add_round("第二回")

    if not rounds:
        return ""
    ordered = [label for label in ["第一回", "第二回"] if label in rounds]
    return " / ".join(ordered)


def _normalize_screening_method_value(value: str) -> str:
    source = str(value or "").translate(FULLWIDTH_ASCII_TRANS).strip()
    if not source:
        return ""
    labels: list[str] = []
    if any(token in source for token in ["書類選考", "書類審査"]) and "書類選考" not in labels:
        labels.append("書類選考")
    if "小論文" in source and "小論文" not in labels:
        labels.append("小論文")
    if re.search(r"校内.{0,8}(単独)?試験|独自試験|個別試験", source) and "校内単独試験" not in labels:
        labels.append("校内単独試験")
    if any(token in source for token in ["学力試験", "個別学力検査", "筆記試験"]) and "学力試験" not in labels:
        labels.append("学力試験")
    if any(token in source for token in ["面接", "面談"]) and "面接" not in labels:
        labels.append("面接")
    if any(token in source for token in ["口頭試問", "口述試験"]) and "口頭試問" not in labels:
        labels.append("口頭試問")
    return " / ".join(labels)


def _normalize_english_requirement(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    raw_evidence = dict(normalized.get("field_evidence") or {}) if isinstance(normalized.get("field_evidence"), dict) else {}
    raw_confidence = dict(normalized.get("field_confidence") or {}) if isinstance(normalized.get("field_confidence"), dict) else {}

    value = str(normalized.get("english_requirement") or "").strip()
    evidence = raw_evidence.get("english_requirement")
    evidence = dict(evidence) if isinstance(evidence, dict) else {}
    evidence_text = str(evidence.get("text") or "").strip()
    combined = " ".join(part for part in [value, evidence_text] if part)
    if not combined:
        return normalized

    if any(noise in combined for noise in ["志望理由書", "提出書類", "学習歴", "学習歴証明", "修学歴", "学歴"]):
        normalized["english_requirement"] = ""
        raw_evidence["english_requirement"] = {"text": "", "page": None}
        raw_confidence["english_requirement"] = min(float(raw_confidence.get("english_requirement") or 0.0), 0.2)
        _append_record_note(normalized, "英語資格の詳細は提出書類欄ではなく原文要件を確認。")
        normalized["field_evidence"] = raw_evidence
        normalized["field_confidence"] = raw_confidence
        return normalized

    source_for_labels = evidence_text if evidence_text else value
    if not _extract_english_labels(source_for_labels):
        source_for_labels = combined
    labels = _extract_english_labels(source_for_labels)

    if labels:
        normalized["english_requirement"] = " / ".join(labels)
        evidence["text"] = source_for_labels
        raw_evidence["english_requirement"] = evidence
        raw_confidence["english_requirement"] = max(float(raw_confidence.get("english_requirement") or 0.0), 0.8)
        _remove_record_notes(normalized, ["英語資格要件は", "英語資格の詳細は"])
    else:
        normalized["english_requirement"] = ""
        raw_evidence["english_requirement"] = {"text": "", "page": None}
        raw_confidence["english_requirement"] = min(float(raw_confidence.get("english_requirement") or 0.0), 0.2)

    note_source = evidence_text or value or combined
    if ENGLISH_NOTE_RE.search(note_source) or any(token in note_source for token in ["いずれか", "提出", "2 つ以上", "２つ以上", "2つ以上"]):
        _append_record_note(normalized, f"英語資格に補足条件あり: {note_source[:120]}")

    normalized["field_evidence"] = raw_evidence
    normalized["field_confidence"] = raw_confidence
    return normalized


def _normalize_eju_fields(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    raw_evidence = dict(normalized.get("field_evidence") or {}) if isinstance(normalized.get("field_evidence"), dict) else {}
    raw_confidence = dict(normalized.get("field_confidence") or {}) if isinstance(normalized.get("field_confidence"), dict) else {}

    def _get_evidence(field: str) -> dict[str, Any]:
        item = raw_evidence.get(field)
        return dict(item) if isinstance(item, dict) else {}

    def _page(field: str) -> int | None:
        try:
            value = _get_evidence(field).get("page")
            return int(value) if value not in ("", None) else None
        except Exception:
            return None

    def _set_field(field: str, value: str, source_text: str = "", confidence: float | None = None) -> None:
        cleaned = _strip_eju_prefix(value)
        normalized[field] = cleaned
        evidence = _get_evidence(field)
        evidence["text"] = str(source_text or evidence.get("text") or cleaned).strip()
        evidence["page"] = evidence.get("page")
        raw_evidence[field] = evidence
        if confidence is not None:
            raw_confidence[field] = confidence

    def _clear_field(field: str) -> None:
        normalized[field] = ""
        raw_evidence[field] = {"text": "", "page": None}
        raw_confidence[field] = min(float(raw_confidence.get(field) or 0.0), 0.18)

    def _looks_like_requirement_context(text: str, label: str) -> bool:
        source = str(text or "").strip()
        if not source:
            return False
        if label not in source:
            return False
        if any(noise in source for noise in ["併願不可", "募集人員", "出願資格", "志望理由書", "提出書類"]):
            return False
        if label == "総合科目" and any(noise in source for noise in ["例", "学部", "のみ", "併願"]):
            if not any(ctx in source for ctx in ["EJU", "日本留学試験", "受験科目", "指定科目", "利用科目"]):
                return False
        return True

    for field in EJU_FIELD_LABELS:
        if str(normalized.get(field) or "").strip():
            canonical = _strip_eju_prefix(_symbol_to_eju_value(field, normalized.get(field) or ""))
            normalized[field] = _normalize_eju_subject_value(field, canonical)

    # Some model outputs pack all EJU requirements into eju_japanese as a numbered list.
    # Example: "①日本語②総合科目、数学(コース1または2)..." .
    # Split the mixed content back into dedicated fields and keep eju_japanese as "日本語".
    jp_source = " ".join(
        part
        for part in [
            str(normalized.get("eju_japanese") or "").strip(),
            str(_get_evidence("eju_japanese").get("text") or "").strip(),
        ]
        if part
    )
    if "日本語" in jp_source and any(token in jp_source for token in ["総合科目", "数学", "理科", "物理", "化学", "生物"]):
        _set_field("eju_japanese", "日本語", jp_source, 0.9)
        if "総合科目" in jp_source and not str(normalized.get("eju_general") or "").strip():
            _set_field("eju_general", "総合科目", jp_source, 0.84)
        if "数学" in jp_source and not str(normalized.get("eju_math") or "").strip():
            _set_field("eju_math", _extract_math_requirement(jp_source), jp_source, 0.82)
        if "物理" in jp_source and not str(normalized.get("eju_physics") or "").strip():
            _set_field("eju_physics", "物理", jp_source, 0.82)
        if "化学" in jp_source and not str(normalized.get("eju_chemistry") or "").strip():
            _set_field("eju_chemistry", "化学", jp_source, 0.82)
        if "生物" in jp_source and not str(normalized.get("eju_biology") or "").strip():
            _set_field("eju_biology", "生物", jp_source, 0.82)
        if "理科" in jp_source and not any(token in jp_source for token in ["物理", "化学", "生物"]):
            _append_record_note(normalized, f"EJU理科存在選択条件: {jp_source[:120]}")

    combined_general = " ".join(
        part for part in [
            str(normalized.get("eju_general") or "").strip(),
            str(_get_evidence("eju_general").get("text") or "").strip(),
        ] if part
    )
    if "総合科目" in combined_general and "数学" in combined_general:
        _set_field("eju_general", "総合科目", combined_general, 0.84)
        if not str(normalized.get("eju_math") or "").strip():
            _set_field("eju_math", _extract_math_requirement(combined_general), combined_general, 0.78)

    # Include eju_general text as science source as many PDFs express science
    # requirements only as "理科（物理・化学）" without filling per-subject cells.
    combined_science = " ".join(
        part
        for field in SCIENCE_FIELDS
        for part in [
            str(normalized.get(field) or "").strip(),
            str(_get_evidence(field).get("text") or "").strip(),
        ]
        if part
    )
    general_science_source = " ".join(
        part
        for part in [
            str(normalized.get("eju_general") or "").strip(),
            str(_get_evidence("eju_general").get("text") or "").strip(),
        ]
        if part
    )
    if general_science_source:
        combined_science = f"{combined_science} {general_science_source}".strip()
    if "理科" in combined_science:
        explicit_fields = [field for field in SCIENCE_FIELDS if EJU_FIELD_LABELS[field] in combined_science]
        if explicit_fields:
            for field in SCIENCE_FIELDS:
                if field in explicit_fields:
                    _set_field(field, EJU_FIELD_LABELS[field], combined_science, 0.8)
                else:
                    _clear_field(field)
        elif any(marker in combined_science for marker in EJU_CHOICE_MARKERS):
            for field in SCIENCE_FIELDS:
                _clear_field(field)
            _append_record_note(normalized, "EJU理科は選択条件あり。個別科目は原文確認。")

    for field, label in EJU_FIELD_LABELS.items():
        combined = " ".join(
            part for part in [
                str(normalized.get(field) or "").strip(),
                str(_get_evidence(field).get("text") or "").strip(),
            ] if part
        )
        if not combined:
            continue
        if field in SCIENCE_FIELDS and label not in combined:
            _clear_field(field)
            continue
        if field == "eju_general" and "総合科目" not in combined:
            _clear_field(field)
            continue
        if field == "eju_general" and not _looks_like_requirement_context(combined, "総合科目"):
            _clear_field(field)
            continue
        if field == "eju_math" and "数学" not in combined:
            _clear_field(field)
            continue
        if field == "eju_math" and not _looks_like_requirement_context(combined, "数学"):
            _clear_field(field)
            continue
        if field != "eju_japanese" and any(token in combined for token in ["TOEFL", "IELTS", "TOEIC"]):
            _clear_field(field)
            continue
        if field == "eju_math" and EJU_NOTE_RE.search(combined):
            _append_record_note(normalized, f"EJU数学に補足条件あり: {combined[:120]}")

    if any(str(normalized.get(field) or "").strip() for field in EJU_FIELD_LABELS):
        _remove_record_notes(normalized, ["EJU科目要件は"])

    normalized["field_evidence"] = raw_evidence
    normalized["field_confidence"] = raw_confidence
    return normalized


def _prepare_record(
    record: dict[str, Any],
    page_map: dict[int, str] | None,
    default_page: int | None,
    university: str,
    year: str,
) -> dict[str, Any]:
    rec = dict(record)
    if university:
        rec["university"] = university
    if year:
        rec["admission_year"] = year
    rec = _normalize_record_noise(rec)

    page_number = rec.get("page_number")
    if page_number in ("", None):
        rec["page_number"] = default_page
        page_number = default_page

    raw_confidence = rec.get("field_confidence") if isinstance(rec.get("field_confidence"), dict) else {}
    raw_evidence = rec.get("field_evidence") if isinstance(rec.get("field_evidence"), dict) else {}
    overall_confidence = float(rec.get("confidence") or 0.0)

    field_confidence: dict[str, float] = {}
    field_evidence: dict[str, dict[str, Any]] = {}

    for field in CRITICAL_FIELDS:
        value = str(rec.get(field) or "").strip()
        evidence_item = raw_evidence.get(field) if isinstance(raw_evidence.get(field), dict) else {}
        evidence_text = str(evidence_item.get("text") or "").strip()
        evidence_page = evidence_item.get("page")
        try:
            evidence_page = int(evidence_page) if evidence_page not in ("", None) else None
        except Exception:
            evidence_page = None

        if page_map:
            inferred = _find_evidence(field, value, page_map, preferred_page=int(page_number) if page_number not in ("", None) else None)
            if value and not evidence_text:
                evidence_text = inferred.get("text") or value
            if value and evidence_page is None:
                evidence_page = inferred.get("page")
        elif value and not evidence_text:
            evidence_text = value

        confidence_value = raw_confidence.get(field)
        try:
            confidence_num = float(confidence_value)
        except Exception:
            confidence_num = 0.0

        if confidence_num <= 0:
            if not value:
                confidence_num = 0.2
            elif evidence_text and value and value in evidence_text:
                confidence_num = max(overall_confidence, 0.86)
            elif evidence_text:
                confidence_num = max(overall_confidence, 0.76)
            else:
                confidence_num = max(overall_confidence, 0.66)

        field_confidence[field] = round(min(max(confidence_num, 0.0), 1.0), 4)
        field_evidence[field] = {
            "text": evidence_text or value,
            "page": evidence_page,
        }

    rec["field_confidence"] = field_confidence
    rec["field_evidence"] = field_evidence
    rec.setdefault("manual_modified_fields", [])
    rec.setdefault("is_reviewed", 0)
    return validate(rec)


def _insert_result(
    doc_id: int,
    result: dict[str, Any],
    page_map: dict[int, str] | None = None,
    default_page: int | None = None,
    university: str = "",
    year: str = "",
) -> int:
    inserted = 0
    # Prefer caller-provided university/year over noisy model output.
    top_univ = university or str(result.get("university") or "").strip()
    top_year = year or str(result.get("admission_year") or "").strip()
    for rec in result.get("records") or []:
        if _is_placeholder_record(rec):
            continue
        validated = _prepare_record(rec, page_map, default_page, top_univ, top_year)
        page_number = validated.get("page_number") or default_page
        insert_staging_record(doc_id, page_number, validated)
        inserted += 1
    return inserted


def _merge_record_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    def score(rec: dict[str, Any]) -> tuple[float, int]:
        filled = sum(1 for v in rec.values() if str(v or "").strip())
        return (float(rec.get("confidence") or 0.0), filled)

    best = max(group, key=score)
    merged = dict(best)
    for rec in group:
        for key, value in rec.items():
            if not str(merged.get(key) or "").strip() and str(value or "").strip():
                merged[key] = value

    depts = []
    seen = set()
    for rec in group:
        dept = str(rec.get("department") or "").strip()
        if dept and dept not in seen:
            seen.add(dept)
            depts.append(dept)
    if depts:
        merged["department"] = " / ".join(depts)
    return merged


def _collapse_keio_faculties(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        if faculty not in groups:
            groups[faculty] = []
            order.append(faculty)
        groups[faculty].append(rec)

    collapsed: list[dict[str, Any]] = []
    for faculty in order:
        group = groups[faculty]
        collapsed.append(group[0] if len(group) == 1 else _merge_record_group(group))
    return collapsed


def _normalize_keio_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    if not str(normalized.get("eju_math") or "").strip():
        normalized["eju_math"] = "?"
    return normalized


def _backfill_science_from_general(record: dict[str, Any]) -> dict[str, Any]:
    """Backfill EJU science split fields when general text carries science details.

    Many PDFs only state science requirements in one phrase like
    "理科（物理・化学）" and leave per-subject cells empty.
    """
    normalized = dict(record)
    evidence = dict(normalized.get("field_evidence") or {}) if isinstance(normalized.get("field_evidence"), dict) else {}
    confidence = dict(normalized.get("field_confidence") or {}) if isinstance(normalized.get("field_confidence"), dict) else {}

    general_source = " ".join(
        part
        for part in [
            str(normalized.get("eju_general") or "").strip(),
            str((evidence.get("eju_general") or {}).get("text") or "").strip(),
            str(normalized.get("_raw_eju_general_source") or "").strip(),
        ]
        if part
    )
    if not general_source:
        return normalized

    has_science_context = ("\u7406\u79d1" in general_source) or any(
        token in general_source for token in ["\u7269\u7406", "\u5316\u5b66", "\u751f\u7269"]
    )
    if not has_science_context:
        return normalized

    for field, label in [("eju_physics", "\u7269\u7406"), ("eju_chemistry", "\u5316\u5b66"), ("eju_biology", "\u751f\u7269")]:
        if label in general_source and not str(normalized.get(field) or "").strip():
            normalized[field] = label
            evidence[field] = {"text": general_source, "page": (evidence.get("eju_general") or {}).get("page")}
            confidence[field] = max(float(confidence.get(field) or 0.0), 0.82)

    if re.search(r"\u3044\u305a\u308c\u304b[1\uff11]\u79d1\u76ee|[1\uff11]\u79d1\u76ee\u3092\u9078\u629e|\u304b\u30891\u79d1\u76ee|\u304b\u3089\uff11\u79d1\u76ee", general_source):
        _append_record_note(normalized, f"EJU理科存在选択条件: {general_source[:120]}")

    normalized["field_evidence"] = evidence
    normalized["field_confidence"] = confidence
    return normalized


def _normalize_record_noise(record: dict[str, Any]) -> dict[str, Any]:
    raw_evidence_source = dict(record.get("field_evidence") or {}) if isinstance(record.get("field_evidence"), dict) else {}
    raw_general_source = " ".join(
        part
        for part in [
            str(record.get("eju_general") or "").strip(),
            str((raw_evidence_source.get("eju_general") or {}).get("text") or "").strip(),
        ]
        if part
    )

    normalized = _normalize_english_requirement(_normalize_eju_fields(record))
    if raw_general_source:
        normalized["_raw_eju_general_source"] = raw_general_source
    normalized = _backfill_science_from_general(normalized)
    normalized.pop("_raw_eju_general_source", None)
    raw_evidence = dict(normalized.get("field_evidence") or {}) if isinstance(normalized.get("field_evidence"), dict) else {}
    application_source = str(normalized.get("application_period") or (raw_evidence.get("application_period") or {}).get("text") or "")
    enrollment_source = str(normalized.get("enrollment_period") or (raw_evidence.get("enrollment_period") or {}).get("text") or "")
    eju_session_source = str((raw_evidence.get("eju_session") or {}).get("text") or normalized.get("eju_session") or "")
    screening_method_source = str((raw_evidence.get("screening_method") or {}).get("text") or normalized.get("screening_method") or "")
    screening_schedule_source = str((raw_evidence.get("screening_schedule") or {}).get("text") or normalized.get("screening_schedule") or "")
    result_date_source = str((raw_evidence.get("result_date") or {}).get("text") or normalized.get("result_date") or "")

    application_period = _normalize_date_expression(application_source, mode="range", strict_date_only=True)
    normalized["application_period"] = application_period
    enrollment_period = _normalize_date_expression(enrollment_source, mode="range", strict_date_only=True)
    normalized["enrollment_period"] = enrollment_period
    eju_session = _normalize_eju_session_value(eju_session_source)
    normalized["eju_session"] = eju_session
    screening_schedule = _normalize_date_expression(screening_schedule_source, mode="list", strict_date_only=True)
    normalized["screening_schedule"] = screening_schedule
    result_date = _normalize_date_expression(result_date_source, mode="list", strict_date_only=True)
    normalized["result_date"] = result_date
    screening_method = _normalize_screening_method_value(screening_method_source)
    normalized["screening_method"] = screening_method
    if normalized.get("screening_schedule"):
        _remove_record_notes(normalized, ["screening_schedule may be missing a valid date"])
    if normalized.get("result_date"):
        _remove_record_notes(normalized, ["result_date may be missing a valid date"])
    eju_japanese = str(normalized.get("eju_japanese") or "").strip()
    if any(token in eju_japanese for token in ["受験票", "PDF", "成績通知書"]):
        normalized["eju_japanese"] = ""

    english = str(normalized.get("english_requirement") or "").strip()
    if english:
        normalized["english_requirement"] = re.sub(r"[、,]?\s*志望理由書等", "", english).strip(" 、,/")
    return normalized


def _backfill_common_fields(records: list[dict[str, Any]], fields: list[str]) -> list[dict[str, Any]]:
    if not records:
        return records

    normalized_records = [_normalize_record_noise(record) for record in records]
    common_values: dict[str, str] = {}
    for field in fields:
        values = [str(record.get(field) or "").strip() for record in normalized_records if str(record.get(field) or "").strip()]
        if not values:
            continue
        value, count = collections.Counter(values).most_common(1)[0]
        if count >= 2:
            common_values[field] = value

    if not common_values:
        return normalized_records

    patched: list[dict[str, Any]] = []
    for record in normalized_records:
        rec = dict(record)
        for field, value in common_values.items():
            if not str(rec.get(field) or "").strip():
                rec[field] = value
        patched.append(rec)
    return patched


def _filter_non_private_student_records(result: dict[str, Any]) -> dict[str, Any]:
    records = []
    for rec in result.get("records") or []:
        text = " ".join(str(rec.get(k) or "") for k in ["admission_period", "faculty", "department", "warnings"])
        if any(flag in text for flag in ["第2種", "帰国生徒", "帰国子女"]):
            continue
        records.append(rec)
    new_result = dict(result)
    new_result["records"] = records
    return new_result


def _dedupe_by_faculty(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_faculty: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        if not faculty:
            continue
        if faculty not in best_by_faculty:
            best_by_faculty[faculty] = rec
            order.append(faculty)
            continue
        prev = best_by_faculty[faculty]
        prev_score = (float(prev.get("confidence") or 0.0), sum(1 for v in prev.values() if str(v or "").strip()))
        cur_score = (float(rec.get("confidence") or 0.0), sum(1 for v in rec.values() if str(v or "").strip()))
        if cur_score > prev_score:
            best_by_faculty[faculty] = rec
    return [best_by_faculty[f] for f in order]


def _supplement_missing_faculties(
    full_text: str,
    university: str,
    year: str,
    target_university: str,
    target_year: str,
    required_faculties: list[str],
    existing_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if university != target_university or str(year) != target_year:
        return existing_records

    merged = list(existing_records)
    chunk_size = 4

    while True:
        existing_faculties = {str(r.get("faculty") or "").strip() for r in merged}
        missing = [f for f in required_faculties if f not in existing_faculties]
        if not missing:
            return _dedupe_by_faculty(merged)

        progressed = False
        for idx in range(0, len(missing), chunk_size):
            batch = missing[idx: idx + chunk_size]
            messages = [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": (
                        f"[Info] university={university} year={year} mode=text-supplement\n\n"
                        "以下の学部だけを補完抽出してください。"
                        "各学部につき1レコード、代表学科名のみ、重複禁止。"
                        "本文に明記がない科目要件や英語資格要件は空欄のままにしてください。"
                        "学部ごとの差異をまとめて一般化しないでください。"
                        "不足学部一覧: "
                        + "、".join(batch)
                        + "。\n\n[全文テキスト]\n"
                        + full_text
                    ),
                },
            ]
            supplement = _call_openai(messages, TEXT_MODEL, max_tokens=2500, token_param="max_completion_tokens")
            extra = supplement.get("records") or []
            filtered = [r for r in extra if str(r.get("faculty") or "").strip() in batch]
            if filtered:
                merged.extend(filtered)
                merged = _dedupe_by_faculty(merged)
                progressed = True

        if not progressed:
            return _dedupe_by_faculty(merged)


def _supplement_meiji_missing_faculties(
    full_text: str,
    university: str,
    year: str,
    existing_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _supplement_missing_faculties(
        full_text=full_text,
        university=university,
        year=year,
        target_university="明治大学",
        target_year="2026",
        required_faculties=MEIJI_REQUIRED_FACULTIES,
        existing_records=existing_records,
    )


def _supplement_waseda_missing_faculties(
    full_text: str,
    university: str,
    year: str,
    existing_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    return _supplement_missing_faculties(
        full_text=full_text,
        university=university,
        year=year,
        target_university="早稲田大学",
        target_year="2026",
        required_faculties=WASEDA_REQUIRED_FACULTIES,
        existing_records=existing_records,
    )


def _find_sparse_pages(page_map: dict[int, str], threshold: int = 200) -> list[int]:
    """Return page numbers whose text content is too short to contain a table."""
    return [page_num for page_num, text in page_map.items() if len(text.strip()) < threshold]


VISION_TABLE_HINTS = (
    "選考方法",
    "試験科目",
    "必要な試験",
    "受験科目",
    "外部試験",
    "日本留学試験",
    "EJU",
    "TOEFL",
    "IELTS",
    "TOEIC",
)


VISION_PATCH_FIELDS = [
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
    "english_requirement",
    "screening_method",
]


def _find_vision_table_pages(page_map: dict[int, str]) -> list[int]:
    pages: list[int] = []
    for page_num, text in page_map.items():
        stripped = text.strip()
        has_hint = any(hint in stripped for hint in VISION_TABLE_HINTS)
        table_signal = any(
            token in stripped
            for token in ["以下の表", "次の表", "下表", "上表", "表で確認", "表を確認", "一覧表"]
        )
        # PDF text layers often lose dense table cells while keeping only the page title.
        if has_hint and (len(stripped) < 700 or table_signal):
            pages.append(page_num)
    return pages


def _record_key(value: str) -> str:
    text = str(value or "").strip()
    for token in [" ", "　", "\t", "\n", "－", "-", "―"]:
        text = text.replace(token, "")
    return text


def _match_patch_record(record: dict[str, Any], patch_by_key: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    faculty = _record_key(str(record.get("faculty") or ""))
    department = _record_key(str(record.get("department") or ""))
    for key in [department, faculty]:
        if key and key in patch_by_key:
            return patch_by_key[key]
    for key, patch in patch_by_key.items():
        if key and (key in department or key in faculty or department in key or faculty in key):
            return patch
    return None


def _merge_patch_record(existing: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = dict(existing)
    for field in ["faculty", "department", "_vision_page", "_vision_variant"]:
        if not str(merged.get(field) or "").strip() and str(incoming.get(field) or "").strip():
            merged[field] = incoming[field]
    for field in VISION_PATCH_FIELDS:
        if not str(merged.get(field) or "").strip() and str(incoming.get(field) or "").strip():
            merged[field] = incoming[field]
    warnings = list(merged.get("warnings") or [])
    for warning in incoming.get("warnings") or []:
        if warning and warning not in warnings:
            warnings.append(str(warning))
    if warnings:
        merged["warnings"] = warnings
    return merged


def _merge_field_metadata(
    record: dict[str, Any],
    field: str,
    value: str,
    page_num: int,
    evidence_text: str,
    confidence: float = 0.74,
) -> None:
    field_evidence = dict(record.get("field_evidence") or {}) if isinstance(record.get("field_evidence"), dict) else {}
    field_confidence = dict(record.get("field_confidence") or {}) if isinstance(record.get("field_confidence"), dict) else {}
    field_evidence[field] = {
        "text": evidence_text,
        "page": page_num,
    }
    field_confidence[field] = confidence
    record["field_evidence"] = field_evidence
    record["field_confidence"] = field_confidence


def _upscale_image(image, factor: float = 1.6):
    try:
        from PIL import Image

        width, height = image.size
        return image.resize((int(width * factor), int(height * factor)), Image.Resampling.LANCZOS)
    except Exception:
        return image


def _vision_patch_image_variants(image_path: Path, out_dir: Path) -> list[tuple[str, Path]]:
    variants: list[tuple[str, Path]] = [("full_page", image_path)]
    try:
        from PIL import Image

        with Image.open(image_path) as img:
            width, height = img.size
            if width <= height * 1.15:
                return variants
            variants = []
            # Wide admissions tables often put faculty names and EJU/English columns
            # on the left half while schedules continue far right. A focused crop
            # keeps the visual path generic without relying on university-specific rules.
            crop_box = (0, 0, int(width * 0.64), height)
            crop_path = out_dir / f"{image_path.stem}_exam_columns.png"
            _upscale_image(img.crop(crop_box)).save(crop_path)
            variants.append(("exam_columns", crop_path))
            if height > 1000:
                split_points = [
                    (0, int(height * 0.43), "exam_columns_top"),
                    (int(height * 0.36), int(height * 0.76), "exam_columns_middle"),
                    (int(height * 0.68), height, "exam_columns_bottom"),
                ]
                for y1, y2, name in split_points:
                    segment_path = out_dir / f"{image_path.stem}_{name}.png"
                    _upscale_image(img.crop((0, y1, int(width * 0.64), y2)), 2.0).save(segment_path)
                    variants.append((name, segment_path))
    except Exception as exc:
        print(f"[direct] vision_patch_crop_skipped {image_path.name}: {exc}")
    return variants


def _vision_patch_records(
    records: list[dict[str, Any]],
    candidate_pages: list[int],
    page_map: dict[int, str],
    pdf_path: Path,
    university: str,
    year: str,
    doc_id: int,
    deadline_ts: float | None = None,
) -> list[dict[str, Any]]:
    """For any records where key fields are empty, re-extract sparse pages via vision
    and backfill missing values. Generic — works for any university."""
    missing_field_ratio = sum(
        1 for r in records
        if any(not str(r.get(field) or "").strip() for field in VISION_PATCH_FIELDS)
    ) / max(len(records), 1)

    if missing_field_ratio < VISION_PATCH_MIN_RATIO or not candidate_pages:
        return records  # quality is fine, skip

    prioritized_pages = list(candidate_pages)[: max(1, VISION_PATCH_MAX_PAGES)]
    print(
        f"[direct] vision_patch triggered: {missing_field_ratio:.0%} records missing table fields, "
        f"pages={prioritized_pages} (cap={VISION_PATCH_MAX_PAGES})"
    )

    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_time_budget(deadline_ts, "vision_patch.render")
    images = render_pdf_to_images(pdf_path, out_dir, pages=prioritized_pages)
    images_by_page = {
        int(path.stem.split("_")[-1]): path
        for path in images
        if path.stem.split("_")[-1].isdigit()
    }

    patch_records: list[dict[str, Any]] = []
    target_units = []
    seen_units = set()
    for record in records:
        faculty = str(record.get("faculty") or "").strip()
        department = str(record.get("department") or "").strip()
        unit = " / ".join(part for part in [faculty, department] if part)
        key = _record_key(unit)
        if unit and key not in seen_units:
            seen_units.add(key)
            target_units.append(unit)
    target_hint = "、".join(target_units[:80])
    for page_num in prioritized_pages:
        _ensure_time_budget(deadline_ts, f"vision_patch.page_{page_num}")
        image_path = images_by_page.get(page_num)
        if not image_path:
            continue
        variants = _vision_patch_image_variants(image_path, out_dir)[: max(1, VISION_PATCH_MAX_VARIANTS)]
        for variant_name, variant_path in variants:
            try:
                _ensure_time_budget(deadline_ts, f"vision_patch.call_{page_num}_{variant_name}")
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You are a conservative admissions table reader. Return strict JSON only. "
                            "Do not invent dates, deadlines, scores, faculties, departments, or requirements."
                        ),
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "text",
                                "text": (
                                    f"[Info] university={university} year={year} mode=vision_patch page={page_num} variant={variant_name}\n"
                                    "このページは学部別の試験科目・選考方法・日程表の可能性があります。"
                                    "文字抽出では表のセルや記号が欠落しやすいため、画像から表を読んでください。"
                                    "学部・学科ごとの日本留学試験(EJU)科目、英語外部資格試験、選考方法を抽出してください。"
                                    f"抽出対象は既存候補にある募集単位だけです: {target_hint}。"
                                    "候補にない学部・学科は出力しないでください。"
                                    "表のヘッダーに記号の意味がある場合は必ず従ってください。"
                                    "○や●が必須を示す列は該当する科目名を値にしてください。"
                                    "▲や△が『いずれか提出必須』を示す場合も該当する科目名を値にしてください。"
                                    "□、■、※、＊、空欄は必須科目として主字段に入れないでください。必要な補足だけ warnings に入れてください。"
                                    "EJU科目は eju_japanese/eju_general/eju_math/eju_physics/eju_chemistry/eju_biology に分けてください。"
                                    "数学は可能なら 数学(コース1), 数学(コース2), 数学(コース1または2) のように書いてください。"
                                    "英語外部資格試験は TOEFL/IELTS/TOEIC など試験名だけを入れ、学習歴や提出書類は入れないでください。"
                                    "この補抽では application_period/deadline_rule/eju_session/screening_schedule/result_date/enrollment_period は空欄でよいです。"
                                    "表に明記されていない日付や締切は絶対に作らないでください。"
                                    "表が複数行に分かれる場合も、募集単位ごとに1 recordを返してください。"
                                    "読み取れないセルは推測せず空欄にしてください。"
                                    "返却形式は {\"records\":[{\"faculty\":\"\",\"department\":\"\",\"eju_japanese\":\"\",\"eju_general\":\"\",\"eju_math\":\"\",\"eju_physics\":\"\",\"eju_chemistry\":\"\",\"eju_biology\":\"\",\"english_requirement\":\"\",\"screening_method\":\"\",\"warnings\":[]}]} のみ。"
                                ),
                            },
                            {
                                "type": "image_url",
                                "image_url": {"url": _data_url_from_image(variant_path)},
                            },
                        ],
                    },
                ]
                result = _call_openai(
                    messages,
                    VISION_MODEL,
                    max_tokens=8000,
                    token_param="max_tokens",
                    request_timeout=_request_timeout(deadline_ts, default_timeout=120),
                )
                for patch_record in result.get("records") or []:
                    tagged = dict(patch_record)
                    tagged["_vision_page"] = page_num
                    tagged["_vision_variant"] = variant_name
                    patch_records.append(tagged)
                print(f"[direct] vision_patch page={page_num} variant={variant_name}: got {len(result.get('records') or [])} records")
            except Exception as e:
                print(f"[direct] vision_patch_failed page={page_num} variant={variant_name}: {e}")
    if not patch_records:
        return records

    patch_by_key: dict[str, dict[str, Any]] = {}
    for pr in patch_records:
        has_signal = any(str(pr.get(field) or "").strip() for field in VISION_PATCH_FIELDS)
        if not has_signal:
            continue
        for key_field in ["department", "faculty"]:
            key = _record_key(str(pr.get(key_field) or ""))
            if key:
                patch_by_key[key] = _merge_patch_record(patch_by_key.get(key, {}), pr)

    patched = []
    for rec in records:
        pr = _match_patch_record(rec, patch_by_key)
        if pr:
            page_num = int(pr.get("_vision_page") or pr.get("page_number") or pr.get("page") or candidate_pages[0])
            pr_field_evidence = pr.get("field_evidence") if isinstance(pr.get("field_evidence"), dict) else {}
            for field in VISION_PATCH_FIELDS:
                patch_value = str(pr.get(field) or "").strip()
                if not patch_value:
                    continue
                current_value = str(rec.get(field) or "").strip()
                if not current_value:
                    field_ev = pr_field_evidence.get(field) if isinstance(pr_field_evidence.get(field), dict) else {}
                    field_ev_text = str(field_ev.get("text") or "").strip() or patch_value
                    rec[field] = patch_value
                    _merge_field_metadata(rec, field, patch_value, page_num, field_ev_text)
                    print(f"[direct] patched {rec.get('faculty')}.{field} = {patch_value!r}")
            warnings = list(rec.get("warnings") or rec.get("warnings_json") or [])
            for warning in pr.get("warnings") or []:
                if warning and warning not in warnings:
                    warnings.append(str(warning))
            if warnings:
                rec["warnings"] = warnings
        patched.append(_normalize_record_noise(rec))
    return patched


def _run_text_path(
    doc_id: int,
    pdf_path: Path,
    university: str,
    year: str,
    deadline_ts: float | None = None,
) -> dict[str, Any]:
    full_text, page_map = _read_pdf_text(pdf_path)
    text_len = len(full_text.strip())
    print(f"[direct] text_length={text_len} pages={len(page_map)}")
    faculty_candidates: list[str] = []
    seen_faculty: set[str] = set()
    for m in re.finditer(r"[一-龥々ぁ-んァ-ンー・]+学部", full_text):
        name = m.group(0).strip()
        if name and name not in seen_faculty:
            seen_faculty.add(name)
            faculty_candidates.append(name)
    faculty_hint = ""
    if faculty_candidates:
        faculty_hint = "本文から検出した学部一覧: " + "、".join(faculty_candidates) + "。この一覧を漏れなくrecordsに含めてください。"

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {
            "role": "user",
            "content": (
                f"[Info] university={university} year={year} mode=text\n\n"
                "これは募集要項PDF全文の文字層です。単ページとして扱わず、全文から募集単位をまとめて抽出してください。"
                "各学部は学部名と代表学科名のみ記載してください。専攻レベルまで細分化しないこと。"
                "同一学部の重複レコードは禁止。各学部につき1レコードのみ出力してください。"
                "PDFに記載された全学部を漏れなく含めてください。records件数は学部数以上にしてください。"
                + faculty_hint +
                "records にはPDF全体の学部・学科ごとの記録を入れてください。"
                "本システムは外国人留学生（私費留学生）の募集要項のみを対象とします。"
                "帰国生徒・帰国子女・第2種に関する情報は抽出しないでください。\n\n"
                "[全文テキスト]\n"
                + full_text
            ),
        },
    ]
    _ensure_time_budget(deadline_ts, "text_path.call")
    result = _call_openai(
        messages,
        TEXT_MODEL,
        max_tokens=12000,
        token_param="max_completion_tokens",
        request_timeout=_request_timeout(deadline_ts, default_timeout=160),
    )
    if university == "明治大学" and str(year) == "2026" and result.get("records"):
        result["records"] = _supplement_meiji_missing_faculties(full_text, university, year, result.get("records") or [])
    if university == "早稲田大学" and str(year) == "2026" and result.get("records"):
        result["records"] = _supplement_waseda_missing_faculties(full_text, university, year, result.get("records") or [])
    if university == "慶應義塾大学" and str(year) == "2026" and result.get("records"):
        result["records"] = [_normalize_keio_record(r) for r in _collapse_keio_faculties(result["records"])]
    if university == "東京大学" and str(year) == "2026" and result.get("records"):
        result = _filter_non_private_student_records(result)
    if not result.get("records"):
        raise RuntimeError("text_path returned 0 records")
    result["records"] = _backfill_common_fields(
        result.get("records") or [],
        ["application_period", "deadline_rule", "eju_session", "enrollment_period"],
    )

    # Text layers are only a fast candidate path. Dense image tables often keep
    # just the section title in text, so critical exam fields must get a vision pass.
    candidate_pages = _find_vision_table_pages(page_map)
    if candidate_pages:
        try:
            result["records"] = _vision_patch_records(
                result.get("records") or [],
                candidate_pages,
                page_map,
                pdf_path,
                university,
                year,
                doc_id,
                deadline_ts=deadline_ts,
            )
            # Vision patch can add sparse records; run one more common-field pass
            # so doc-level constants (like EJU session) stay complete.
            result["records"] = _backfill_common_fields(
                result.get("records") or [],
                ["application_period", "deadline_rule", "eju_session", "enrollment_period"],
            )
        except TimeoutError as e:
            print(f"[direct] vision_patch_skipped_due_to_budget: {e}")

    inserted = _insert_result(doc_id, result, page_map=page_map, university=university, year=year)
    return {
        "mode": "text",
        "pages": len(page_map),
        "text_length": text_len,
        "records": len(result.get("records") or []),
        "inserted": inserted,
        "failed_pages": [],
        "raw": result,
    }


def _run_vision_path(
    doc_id: int,
    pdf_path: Path,
    university: str,
    year: str,
    deadline_ts: float | None = None,
) -> dict[str, Any]:
    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    _ensure_time_budget(deadline_ts, "vision_path.render")
    images = render_pdf_to_images(pdf_path, out_dir)
    page_map = extract_text_per_page(pdf_path)
    inserted = 0
    failed_pages: list[dict[str, Any]] = []
    last_raw: dict[str, Any] | None = None

    for page_num, image_path in enumerate(images, start=1):
        if deadline_ts is not None and _remaining_seconds(deadline_ts) is not None and _remaining_seconds(deadline_ts) <= 0:
            failed_pages.append({"page": page_num, "error": "time budget exceeded"})
            print(f"[direct] vision_budget_stop at page={page_num}")
            break
        try:
            messages = [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"[Info] university={university} year={year} mode=vision page={page_num}\n"
                                "これは単ページPDF画像です。ページ中の募集単位をまとめて JSON で返してください。"
                                "本システムは外国人留学生（私費留学生）の募集要項のみを対象とします。"
                                "帰国生徒・帰国子女・第2種に関する情報は抽出しないでください。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url_from_image(image_path)},
                        },
                    ],
                },
            ]
            result = _call_openai(
                messages,
                VISION_MODEL,
                max_tokens=12000,
                token_param="max_tokens",
                request_timeout=_request_timeout(deadline_ts, default_timeout=120),
            )
            if university == "慶應義塾大学" and str(year) == "2026" and result.get("records"):
                result["records"] = [_normalize_keio_record(r) for r in _collapse_keio_faculties(result["records"])]
            if university == "東京大学" and str(year) == "2026" and result.get("records"):
                result = _filter_non_private_student_records(result)
            records = result.get("records") or []
            for rec in records:
                if _is_placeholder_record(rec):
                    continue
                validated = _prepare_record(
                    rec,
                    {page_num: page_map.get(page_num, "")},
                    page_num,
                    university,
                    year,
                )
                insert_staging_record(doc_id, page_num, validated)
                inserted += 1
            last_raw = result
        except Exception as e:
            failed_pages.append({"page": page_num, "error": str(e)})
            print(f"[direct] vision_failed page={page_num}: {e}")

    return {
        "mode": "vision",
        "pages": len(images),
        "records": inserted,
        "inserted": inserted,
        "failed_pages": failed_pages,
        "raw": last_raw,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Direct PDF-to-LLM extractor")
    p.add_argument("--pdf", required=True)
    p.add_argument("--university", required=True)
    p.add_argument("--year", required=True)
    p.add_argument("--url", default="")
    return p


def run_extraction(
    pdf_path: Path,
    university: str,
    year: str,
    url: str = "",
    max_seconds: int | None = None,
) -> dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    init_db()
    provided_university = _clean_university_name(university)
    preview_text, _ = _read_pdf_text(pdf_path)
    inferred_university = provided_university or _infer_university_from_pdf(pdf_path, preview_text, url)
    stored_university = inferred_university or AUTO_UNIVERSITY_PLACEHOLDER
    working_university = inferred_university or ""
    doc_id = create_source_document(
        university=stored_university,
        file_name=pdf_path.name,
        file_path=str(pdf_path),
        pdf_url=url,
        admission_year=year,
    )
    print(f"[direct] source_document id={doc_id}")
    effective_max_seconds = EXTRACT_MAX_SECONDS if max_seconds is None else int(max_seconds)
    deadline_ts = time.monotonic() + effective_max_seconds if effective_max_seconds and effective_max_seconds > 0 else None

    full_text = preview_text
    report: dict[str, Any]
    failed_pages: list[dict[str, Any]] = []
    if len(full_text.strip()) > 500:
        try:
            report = _run_text_path(doc_id, pdf_path, working_university, year, deadline_ts=deadline_ts)
            status = "text_completed"
        except Exception as e:
            print(f"[direct] text_path_failed: {e}")
            failed_pages.append({"stage": "text_path", "error": str(e)})
            try:
                report = _run_vision_path(doc_id, pdf_path, working_university, year, deadline_ts=deadline_ts)
                status = "vision_completed"
            except TimeoutError as te:
                print(f"[direct] budget_exceeded_after_text_failure: {te}")
                report = {
                    "mode": "budget_stop",
                    "pages": 0,
                    "records": 0,
                    "inserted": 0,
                    "failed_pages": [],
                    "raw": {},
                }
                status = "budget_exceeded"
                failed_pages.append({"stage": "vision_path", "error": str(te)})
    else:
        try:
            report = _run_vision_path(doc_id, pdf_path, working_university, year, deadline_ts=deadline_ts)
            status = "vision_completed"
        except TimeoutError as te:
            print(f"[direct] budget_exceeded_in_vision_path: {te}")
            report = {
                "mode": "budget_stop",
                "pages": 0,
                "records": 0,
                "inserted": 0,
                "failed_pages": [],
                "raw": {},
            }
            status = "budget_exceeded"
            failed_pages.append({"stage": "vision_path", "error": str(te)})

    final_university = _pick_final_university(report.get("raw"), stored_university)
    update_source_document(doc_id, status=status, university=final_university)
    duplicate_cleanup = prune_duplicate_documents(doc_id)
    return {
        "doc_id": doc_id,
        "status": status,
        "university": final_university,
        "duplicate_cleanup": duplicate_cleanup,
        "mode": report["mode"],
        "pages": report.get("pages"),
        "records": report.get("records"),
        "inserted": report.get("inserted"),
        "failed_pages": failed_pages + list(report.get("failed_pages", [])),
        "max_seconds": effective_max_seconds,
    }


def main() -> int:
    args = build_parser().parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"[direct] PDF not found: {pdf_path}")
        return 2
    result = run_extraction(pdf_path, args.university, str(args.year), args.url or "")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
