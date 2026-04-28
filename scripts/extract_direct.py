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

from scripts.db import create_source_document, init_db, insert_staging_record, update_source_document  # noqa: E402
from scripts.json_parser import extract_json_payload  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.validator import CRITICAL_FIELDS, validate  # noqa: E402

PROMPT_PATH = ROOT / "prompts" / "vision_prompt.md"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
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


def _load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return key


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


TEXT_MODEL = _load_env_value("OPENAI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
VISION_MODEL = _load_env_value("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)


def _read_pdf_text(pdf_path: Path) -> tuple[str, dict[int, str]]:
    page_map = extract_text_per_page(pdf_path)
    texts = [f"=== PAGE {idx} ===\\n{text}" for idx, text in sorted(page_map.items()) if text]
    return "\\n\\n".join(texts), page_map


def _clean_university_name(value: str) -> str:
    cleaned = re.sub(r"\s+", "", str(value or "").strip())
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
) -> dict[str, Any]:
    api_key = _load_api_key()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        token_param: max_tokens,
    }
    req = urllib_request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib_request.urlopen(req, timeout=240) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < 2:
                time.sleep(2.0 + attempt * 2.0)
                last_error = RuntimeError(f"OpenAI API error {e.code}: {body}")
                continue
            raise RuntimeError(f"OpenAI API error {e.code}: {body}") from e
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.5 + attempt)
                continue
            raise
    else:
        if last_error:
            raise last_error
        raise RuntimeError("OpenAI request failed")

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
    (r"Duolingo(?: English Test)?|DET", "Duolingo English Test"),
    (r"TEAP", "TEAP"),
    (r"英検", "英検"),
    (r"TCF", "TCF"),
    (r"DELF", "DELF"),
    (r"DALF", "DALF"),
    (r"Goethe-Zertifikat", "Goethe-Zertifikat"),
    (r"ÖSD(?: Zertifikat)?|OSD(?: Zertifikat)?", "ÖSD"),
]
ENGLISH_NOTE_RE = re.compile(r"([0-9０-９]{1,3}(?:\.[0-9０-９]+)?\s*点以上|基準点なし|出願基準点なし|免除|換算|CEFR|相当)")


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

    if "志望理由書" in evidence_text or "提出書類" in evidence_text:
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
            normalized[field] = _strip_eju_prefix(normalized.get(field) or "")

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

    combined_science = " ".join(
        part for field in SCIENCE_FIELDS
        for part in [
            str(normalized.get(field) or "").strip(),
            str(_get_evidence(field).get("text") or "").strip(),
        ] if part
    )
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


def _normalize_record_noise(record: dict[str, Any]) -> dict[str, Any]:
    normalized = _normalize_english_requirement(_normalize_eju_fields(record))
    eju_japanese = str(normalized.get("eju_japanese") or "").strip()
    if any(token in eju_japanese for token in ["受験票", "PDF", "成績通知書"]):
        normalized["eju_japanese"] = ""

    english = str(normalized.get("english_requirement") or "").strip()
    if english:
        normalized["english_requirement"] = re.sub(r"[、,]?\s*志望理由書等", "", english).strip(" 、,/")
    if str(normalized.get("university") or "").strip() == "早稲田大学" and str(normalized.get("faculty") or "").strip() == "人間科学部":
        raw_evidence = dict(normalized.get("field_evidence") or {}) if isinstance(normalized.get("field_evidence"), dict) else {}
        raw_confidence = dict(normalized.get("field_confidence") or {}) if isinstance(normalized.get("field_confidence"), dict) else {}
        if not str(normalized.get("eju_math") or "").strip():
            note_text = str(normalized.get("screening_method") or normalized.get("screening_schedule") or "").strip()
            normalized["eju_math"] = "数学"
            raw_evidence["eju_math"] = {"text": note_text, "page": None}
            raw_confidence["eju_math"] = max(float(raw_confidence.get("eju_math") or 0.0), 0.58)
        normalized["field_evidence"] = raw_evidence
        normalized["field_confidence"] = raw_confidence
        _append_record_note(normalized, "EJU数学に一次選考免除条件あり。原文確認。")
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


def _vision_patch_records(
    records: list[dict[str, Any]],
    sparse_pages: list[int],
    pdf_path: Path,
    university: str,
    year: str,
    doc_id: int,
) -> list[dict[str, Any]]:
    """For any records where key fields are empty, re-extract sparse pages via vision
    and backfill missing values. Generic — works for any university."""
    PATCH_FIELDS = ["english_requirement", "eju_japanese", "eju_math", "screening_method"]

    empty_ratio = sum(
        1 for r in records
        if not str(r.get("english_requirement") or "").strip()
    ) / max(len(records), 1)

    if empty_ratio < 0.3 or not sparse_pages:
        return records  # quality is fine, skip

    print(f"[direct] vision_patch triggered: {empty_ratio:.0%} records missing english_requirement, sparse_pages={sparse_pages}")

    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = render_pdf_to_images(pdf_path, out_dir)

    # Only render and send the sparse pages
    patch_records: list[dict[str, Any]] = []
    for page_num in sparse_pages:
        img_idx = page_num - 1
        if img_idx >= len(images):
            continue
        image_path = images[img_idx]
        try:
            messages = [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"[Info] university={university} year={year} mode=vision_patch page={page_num}\n"
                                "このページは表が画像化されています。"
                                "学部・学科ごとの英語外部試験要件・EJU要件を中心に抽出してください。"
                                "各レコードに faculty と english_requirement を必ず含めてください。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url_from_image(image_path)},
                        },
                    ],
                },
            ]
            result = _call_openai(messages, VISION_MODEL, max_tokens=6000, token_param="max_tokens")
            patch_records.extend(result.get("records") or [])
            print(f"[direct] vision_patch page={page_num}: got {len(result.get('records') or [])} records")
        except Exception as e:
            print(f"[direct] vision_patch_failed page={page_num}: {e}")

    if not patch_records:
        return records

    # Build lookup: faculty -> patch record
    patch_by_faculty: dict[str, dict[str, Any]] = {}
    for pr in patch_records:
        faculty = str(pr.get("faculty") or "").strip()
        if faculty:
            patch_by_faculty[faculty] = pr

    # Backfill empty fields in existing records
    patched = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        pr = patch_by_faculty.get(faculty)
        if pr:
            for field in PATCH_FIELDS:
                if not str(rec.get(field) or "").strip() and str(pr.get(field) or "").strip():
                    rec[field] = pr[field]
                    print(f"[direct] patched {faculty}.{field} = {pr[field]!r}")
        patched.append(rec)
    return patched


def _run_text_path(doc_id: int, pdf_path: Path, university: str, year: str) -> dict[str, Any]:
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
    result = _call_openai(messages, TEXT_MODEL, max_tokens=12000, token_param="max_completion_tokens")
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

    # Generic vision patch for image-based tables
    sparse_pages = _find_sparse_pages(page_map)
    if sparse_pages:
        result["records"] = _vision_patch_records(
            result.get("records") or [],
            sparse_pages,
            pdf_path,
            university,
            year,
            doc_id,
        )

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


def _run_vision_path(doc_id: int, pdf_path: Path, university: str, year: str) -> dict[str, Any]:
    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = render_pdf_to_images(pdf_path, out_dir)
    page_map = extract_text_per_page(pdf_path)
    inserted = 0
    failed_pages: list[dict[str, Any]] = []
    last_raw: dict[str, Any] | None = None

    for page_num, image_path in enumerate(images, start=1):
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
            result = _call_openai(messages, VISION_MODEL, max_tokens=12000, token_param="max_tokens")
            if university == "慶應義塾大学" and str(year) == "2026" and result.get("records"):
                result["records"] = [_normalize_keio_record(r) for r in _collapse_keio_faculties(result["records"])]
            if university == "東京大学" and str(year) == "2026" and result.get("records"):
                result = _filter_non_private_student_records(result)
            records = result.get("records") or []
            for rec in records:
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


def run_extraction(pdf_path: Path, university: str, year: str, url: str = "") -> dict[str, Any]:
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

    full_text = preview_text
    if len(full_text.strip()) > 500:
        try:
            report = _run_text_path(doc_id, pdf_path, working_university, year)
            status = "text_completed"
        except Exception as e:
            print(f"[direct] text_path_failed: {e}")
            report = _run_vision_path(doc_id, pdf_path, working_university, year)
            status = "vision_completed"
    else:
        report = _run_vision_path(doc_id, pdf_path, working_university, year)
        status = "vision_completed"

    final_university = _pick_final_university(report.get("raw"), stored_university)
    update_source_document(doc_id, status=status, university=final_university)
    return {
        "doc_id": doc_id,
        "status": status,
        "university": final_university,
        "mode": report["mode"],
        "pages": report.get("pages"),
        "records": report.get("records"),
        "inserted": report.get("inserted"),
        "failed_pages": report.get("failed_pages", []),
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
