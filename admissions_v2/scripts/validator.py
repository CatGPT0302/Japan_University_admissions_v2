"""
Validator and metadata helpers for admission_records_staging.
Risk-aware and conservative: prefer explicit review flags over silent guesses.
"""
from __future__ import annotations

import re
from typing import Any

CRITICAL_FIELDS = [
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

HIGH_RISK_FIELDS = [
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
    "screening_schedule",
    "result_date",
    "enrollment_period",
]

EJU_FIELD_KEYS = [
    "eju_japanese",
    "eju_general",
    "eju_math",
    "eju_physics",
    "eju_chemistry",
    "eju_biology",
]

DATE_PATTERN = re.compile(r"(20\d{2})[年\-.]?\d{1,2}[月\-.]?\d{1,2}")
EJU_FORBIDDEN = {"TOEFL", "IELTS", "TOEIC"}
ENGLISH_FORBIDDEN = {"日本語", "総合科目", "数学", "物理", "化学", "生物"}
NOT_APPLICABLE_MARKERS = {
    "なし",
    "不要",
    "該当なし",
    "課さない",
    "問わない",
    "任意",
    "出願基準点なし",
    "基準点なし",
}


def _s(v: Any) -> str:
    return str(v or "").strip()


def _contains_any(text: str, tokens: set[str] | list[str] | tuple[str, ...]) -> bool:
    return any(token for token in tokens if token and token in text)


def _clamp_confidence(value: Any, default: float = 0.0) -> float:
    try:
        num = float(value)
    except Exception:
        num = default
    if num < 0:
        return 0.0
    if num > 1:
        return 1.0
    return round(num, 4)


def normalize_field_confidence(raw: Any) -> dict[str, float]:
    data = raw if isinstance(raw, dict) else {}
    normalized: dict[str, float] = {}
    for field in CRITICAL_FIELDS:
        normalized[field] = _clamp_confidence(data.get(field), 0.0)
    return normalized


def normalize_field_evidence(raw: Any) -> dict[str, dict[str, Any]]:
    data = raw if isinstance(raw, dict) else {}
    normalized: dict[str, dict[str, Any]] = {}
    # Reviewable metadata also needs provenance, even when it is not risk-scored.
    extra_fields = (
        "university", "admission_year", "admission_period", "faculty", "department",
        "prefecture", "campus", "required_documents", "eligibility", "evidence",
    )
    fields = [*CRITICAL_FIELDS, *(field for field in extra_fields if field in data)]
    for field in fields:
        item = data.get(field)
        if isinstance(item, dict):
            text = _s(item.get("text"))
            page = item.get("page")
        else:
            text = _s(item)
            page = None
        if page in ("", None):
            page = None
        else:
            try:
                page = int(page)
            except Exception:
                page = None
        normalized[field] = {
            "text": text,
            "page": page,
        }
    return normalized


def normalize_manual_modified_fields(raw: Any) -> list[str]:
    if isinstance(raw, list):
        values = [str(item).strip() for item in raw if str(item).strip()]
    else:
        values = []
    return list(dict.fromkeys(values))


def _field_text_bundle(record: dict[str, Any], field_evidence: dict[str, dict[str, Any]], field: str) -> str:
    parts = [
        _s(record.get(field)),
        _s(field_evidence.get(field, {}).get("text")),
    ]
    return " ".join(part for part in parts if part)


def _is_optional_empty_field(record: dict[str, Any], field_evidence: dict[str, dict[str, Any]], field: str) -> bool:
    value = _s(record.get(field))
    evidence_text = _s(field_evidence.get(field, {}).get("text"))
    combined = _field_text_bundle(record, field_evidence, field)
    if value or evidence_text:
        return _contains_any(combined, NOT_APPLICABLE_MARKERS)

    if field == "deadline_rule":
        return bool(_s(record.get("application_period")))

    if field == "eju_japanese":
        context = " ".join(
            [
                _s(record.get("eju_session")),
                _field_text_bundle(record, field_evidence, "eju_general"),
                _field_text_bundle(record, field_evidence, "eju_math"),
                _field_text_bundle(record, field_evidence, "eju_physics"),
                _field_text_bundle(record, field_evidence, "eju_chemistry"),
                _field_text_bundle(record, field_evidence, "eju_biology"),
            ]
        )
        return bool(context)

    if field in {"eju_physics", "eju_chemistry", "eju_biology"}:
        sibling_bundle = " ".join(
            _field_text_bundle(record, field_evidence, key)
            for key in EJU_FIELD_KEYS
            if key != field
        )
        return bool(sibling_bundle or _s(record.get("eju_session")))

    if field == "eju_math":
        sibling_bundle = " ".join(
            _field_text_bundle(record, field_evidence, key)
            for key in ["eju_general", "eju_physics", "eju_chemistry", "eju_biology"]
        )
        return bool(sibling_bundle or _s(record.get("eju_session")))

    if field == "eju_general":
        sibling_bundle = " ".join(
            _field_text_bundle(record, field_evidence, key)
            for key in ["eju_math", "eju_physics", "eju_chemistry", "eju_biology"]
        )
        return bool(sibling_bundle or _s(record.get("eju_session")))

    if field == "english_requirement":
        context = " ".join(
            [
                _s(record.get("screening_method")),
                _s(record.get("screening_schedule")),
                _s(record.get("faculty")),
                _s(record.get("department")),
            ]
        )
        return bool(context)

    return False


def compute_risk_level(field_confidence: dict[str, float]) -> str:
    high_risk_scores = [field_confidence.get(field, 0.0) for field in HIGH_RISK_FIELDS]
    if any(score < 0.6 for score in high_risk_scores):
        return "high"
    if any(score < 0.8 for score in high_risk_scores):
        return "medium"
    return "low"


def _ensure_field_metadata(record: dict[str, Any]) -> tuple[dict[str, float], dict[str, dict[str, Any]]]:
    field_confidence = normalize_field_confidence(record.get("field_confidence"))
    field_evidence = normalize_field_evidence(record.get("field_evidence"))

    overall_confidence = _clamp_confidence(record.get("confidence"), 0.0)
    if overall_confidence <= 0:
        nonzero = [score for score in field_confidence.values() if score > 0]
        overall_confidence = round(sum(nonzero) / len(nonzero), 4) if nonzero else 0.0

    for field in CRITICAL_FIELDS:
        value = _s(record.get(field))
        evidence = field_evidence[field]
        if value and not evidence["text"]:
            evidence["text"] = value

        current = field_confidence.get(field, 0.0)
        if not value and _is_optional_empty_field(record, field_evidence, field):
            field_confidence[field] = max(current, 0.88)
            continue
        if current > 0:
            continue

        if not value:
            field_confidence[field] = 0.2
        elif evidence["text"] and evidence["text"] != value:
            field_confidence[field] = max(overall_confidence, 0.82)
        elif evidence["text"]:
            field_confidence[field] = max(overall_confidence, 0.74)
        else:
            field_confidence[field] = max(overall_confidence, 0.68)

    return field_confidence, field_evidence


def validate(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    warnings: list[str] = list(r.get("warnings") or r.get("warnings_json") or [])

    faculty = _s(r.get("faculty"))
    department = _s(r.get("department"))
    application_period = _s(r.get("application_period"))
    eju_japanese = _s(r.get("eju_japanese"))
    eju_general = _s(r.get("eju_general"))
    eju_math = _s(r.get("eju_math"))
    english = _s(r.get("english_requirement"))
    screening_schedule = _s(r.get("screening_schedule"))
    result_date = _s(r.get("result_date"))

    field_confidence, field_evidence = _ensure_field_metadata(r)
    risk_level = compute_risk_level(field_confidence)
    nonzero_scores = [score for score in field_confidence.values() if score > 0]
    confidence = round(sum(nonzero_scores) / len(nonzero_scores), 4) if nonzero_scores else _clamp_confidence(
        r.get("confidence"),
        0.0,
    )

    if not faculty:
        warnings.append("faculty is empty")
    if not department:
        warnings.append("department is empty")
    if not application_period:
        warnings.append("application_period is empty")

    for field_name, field_val in [("screening_schedule", screening_schedule), ("result_date", result_date)]:
        if field_val and "要確認" not in field_val and not DATE_PATTERN.search(field_val):
            warnings.append(f"{field_name} may be missing a valid date")

    if not screening_schedule and not result_date:
        warnings.append("screening schedule and result date are both empty")

    eju_combined = " ".join([eju_japanese, eju_general, eju_math])
    if any(token in eju_combined for token in EJU_FORBIDDEN):
        warnings.append("EJU fields may contain English test content")

    if any(token in english for token in ENGLISH_FORBIDDEN):
        warnings.append("english_requirement may contain EJU subject content")

    if risk_level == "high":
        warnings.append("high risk record")
    elif risk_level == "medium":
        warnings.append("medium risk record")

    r["field_confidence"] = field_confidence
    r["field_evidence"] = field_evidence
    r["risk_level"] = risk_level
    r["confidence"] = confidence
    r["warnings_json"] = list(dict.fromkeys(warnings))
    r["needs_review"] = bool(warnings) or risk_level in {"high", "medium"}
    r["manual_modified_fields"] = normalize_manual_modified_fields(r.get("manual_modified_fields"))
    r["is_reviewed"] = 1 if bool(r.get("is_reviewed")) else 0
    if r["is_reviewed"] and not r.get("reviewed_at"):
        r["reviewed_at"] = r.get("updated_at") or ""
    return r
