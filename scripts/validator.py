"""
Validator for admission_records_staging.
Accuracy-first: prefer NULL/warning over wrong value.
"""
from __future__ import annotations

import re
from typing import Any

DATE_PATTERN = re.compile(r"(20\d{2})[年/]\d{1,2}[月/]\d{1,2}")
EJU_FORBIDDEN = {"TOEFL", "IELTS", "TOEIC"}
ENGLISH_FORBIDDEN = {"日本語", "総合科目", "数学", "理科", "物理", "化学", "生物"}


def _s(v: Any) -> str:
    return str(v or "").strip()


def validate(record: dict[str, Any]) -> dict[str, Any]:
    r = dict(record)
    warnings: list[str] = list(r.get("warnings") or [])

    faculty = _s(r.get("faculty"))
    department = _s(r.get("department"))
    application_period = _s(r.get("application_period"))
    eju_japanese = _s(r.get("eju_japanese"))
    eju_general = _s(r.get("eju_general"))
    eju_math = _s(r.get("eju_math"))
    english = _s(r.get("english_requirement"))
    screening_schedule = _s(r.get("screening_schedule"))
    result_date = _s(r.get("result_date"))
    confidence = float(r.get("confidence") or 0.0)

    # ── Required fields ──────────────────────────────────────────
    if not faculty:
        warnings.append("faculty が空欄です。")
    if not department:
        warnings.append("department が空欄です。")
    if not application_period:
        warnings.append("application_period が空欄です。")

    # ── Date sanity check ────────────────────────────────────────
    for field_name, field_val in [("screening_schedule", screening_schedule),
                                   ("result_date", result_date)]:
        if field_val and "要確認" not in field_val and not DATE_PATTERN.search(field_val):
            warnings.append(f"{field_name} に日付が見当たりません。")

    if not screening_schedule and not result_date:
        warnings.append("選考日程・合格発表日がどちらも空欄です。")

    # ── Field confusion checks ───────────────────────────────────
    eju_combined = " ".join([eju_japanese, eju_general, eju_math])
    if any(t in eju_combined for t in EJU_FORBIDDEN):
        warnings.append("EJUフィールドに英語試験名が混入しています（フィールド混淆）。")

    if any(t in english for t in ENGLISH_FORBIDDEN):
        warnings.append("英語フィールドに日本語試験科目が混入しています（フィールド混淆）。")

    # ── Confidence threshold ─────────────────────────────────────
    if confidence < 0.85:
        warnings.append(f"confidence={confidence:.2f} < 0.85。")

    # ── 要確認 flag ───────────────────────────────────────────────
    all_text = " ".join(_s(v) for v in r.values())
    if "要確認" in all_text:
        warnings.append("フィールド内に「要確認」が含まれています。")

    # ── Deduplicate and write back ────────────────────────────────
    r["warnings_json"] = list(dict.fromkeys(warnings))
    r["needs_review"] = bool(warnings) or confidence < 0.85
    return r
