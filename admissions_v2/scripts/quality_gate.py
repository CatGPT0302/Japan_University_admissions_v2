from __future__ import annotations

from typing import Any, Callable


GHOST_FACULTIES = {"出願期間前", "出願期間中", "出願期間後", "合格後"}
REQUIRED_FOR_QUALITY = ["faculty", "application_period", "eju_session", "screening_method"]


def evaluate_quality(
    chinese_records: list[dict[str, Any]],
    *,
    to_internal_records: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
    parse_error: str = "",
    finish_reason: str = "",
    extra_warnings: list[str] | None = None,
) -> dict[str, Any]:
    warnings: list[str] = list(extra_warnings or [])
    status = "ok"
    if parse_error:
        return {
            "quality_status": "failed",
            "quality_message": f"模型输出无法解析：{parse_error}",
            "warnings": [parse_error],
        }
    if "length" in finish_reason:
        status = "needs_review"
        warnings.append("模型输出可能被截断，请人工复核记录完整性。")
    if not chinese_records:
        return {
            "quality_status": "failed",
            "quality_message": "没有抽取到任何记录，请检查PDF或模型返回。",
            "warnings": ["没有抽取到任何记录"],
        }

    internal = to_internal_records(chinese_records)
    record_warning_count = sum(1 for rec in internal if rec.get("warnings") or rec.get("needs_review"))
    if record_warning_count:
        status = "needs_review"
        warnings.append(f"{record_warning_count} 条记录带有模型复核提示")

    ghost = sorted({rec["faculty"] for rec in internal if rec.get("faculty") in GHOST_FACULTIES})
    if ghost:
        status = "needs_review"
        warnings.append("疑似目录标题被抽成学部：" + "、".join(ghost))

    missing_rates: list[str] = []
    for field in REQUIRED_FOR_QUALITY:
        missing = sum(1 for rec in internal if not str(rec.get(field) or "").strip())
        rate = missing / max(len(internal), 1)
        if rate >= 0.5:
            status = "needs_review"
            missing_rates.append(f"{field} 空值率 {rate:.0%}")
    if missing_rates:
        warnings.append("关键字段缺失偏高：" + "；".join(missing_rates))

    if warnings:
        status = "needs_review"

    if status == "ok":
        message = f"抽取完成，共 {len(chinese_records)} 条记录；可进入人工复核。"
    else:
        message = f"抽取完成，共 {len(chinese_records)} 条记录；可进入人工复核，但需要重点检查：" + "；".join(warnings)
    return {"quality_status": status, "quality_message": message, "warnings": warnings}
