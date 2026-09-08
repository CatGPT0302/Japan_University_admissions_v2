from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.source_review_state import load_source_review_states, source_review_item_id  # noqa: E402


def load_review_queue(*, root: Path = ROOT, path: Path | None = None) -> dict[str, Any]:
    queue_path = path or root / "data" / "source_review_queue.json"
    if not queue_path.exists():
        return {"generated_at": "", "summary": {"needs_review": 0}, "items": []}
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {"generated_at": "", "summary": {"needs_review": 0}, "items": []}


def _action_for_status(status: str) -> str:
    if status == "changed":
        return "打开官方资料，对照当前已确认内容，判断是否需要重新整理。"
    if status == "marker_mismatch":
        return "先确认链接是否仍然指向这所学校的留学生招生资料。"
    if status == "not_pdf":
        return "学校可能换了资料形式，先手动打开官网确认。"
    if status == "failed":
        return "这次没有检查成功，稍后重试或手动打开官网。"
    if status == "first_check":
        return "这是第一次记录到来源内容，请确认来源正确后再接受为新的来源凭据。"
    return "查看来源状态。"


def _status_label(status: str) -> str:
    if status == "changed":
        return "官方资料有变化"
    if status == "marker_mismatch":
        return "来源内容不匹配"
    if status == "not_pdf":
        return "链接形式需要确认"
    if status == "failed":
        return "检查失败"
    if status == "first_check":
        return "新来源待确认"
    return "需要查看"


def _likely_changed_areas(item: dict[str, Any]) -> list[str]:
    status = str(item.get("status") or "")
    markers = [str(marker) for marker in item.get("missing_markers") or [] if str(marker).strip()]
    areas: list[str] = []
    marker_text = " ".join(markers)
    marker_lower = marker_text.lower()
    if any(token in marker_lower for token in ["eju", "日本留学試験", "日本留学"]):
        areas.append("EJU 要求")
    if any(token in marker_lower for token in ["english", "toefl", "toeic", "ielts", "英語", "英语"]):
        areas.append("英语要求")
    if any(token in marker_text for token in ["出願", "締切", "期間", "受付", "申请", "报名"]):
        areas.append("申请时间")
    if any(token in marker_text for token in ["試験", "選考", "面接", "考试", "面试"]):
        areas.append("考试安排")
    if status == "changed" and not areas:
        areas.extend(["申请时间", "考试要求", "提交材料"])
    if status == "marker_mismatch" and not areas:
        areas.append("来源链接")
    if status in {"not_pdf", "failed", "first_check"} and not areas:
        areas.append("官网来源")
    return areas[:4]


def _owner_summary(item: dict[str, Any]) -> str:
    university = item.get("university") or item.get("stem") or "这份来源"
    year = item.get("admission_year") or "未标年度"
    status = str(item.get("status") or "")
    label = _status_label(status)
    if status == "changed":
        return f"{university}（{year}）的官方资料内容已经变化，需要人工看一眼后再决定是否重新整理。"
    if status == "marker_mismatch":
        return f"{university}（{year}）的来源能打开，但没有找到预期的招生内容，可能是链接或页面位置变了。"
    if status == "not_pdf":
        return f"{university}（{year}）的来源不再像 PDF，需要确认学校是否改成网页或换了文件。"
    if status == "failed":
        return f"{university}（{year}）这次没有检查成功，正式资料未被改动。"
    if status == "first_check":
        return f"{university}（{year}）已经抓到来源内容，但还没有正式来源凭据，需要人工确认后再接受。"
    return f"{university}（{year}）{label}，需要人工确认下一步。"


def _next_steps(item: dict[str, Any]) -> list[str]:
    status = str(item.get("status") or "")
    if status == "changed":
        return ["打开官网资料", "对照当前已确认内容", "需要更新时点击重新整理并复审"]
    if status == "marker_mismatch":
        return ["打开官网资料", "确认是否仍是留学生招生页面", "必要时更新来源登记"]
    if status == "not_pdf":
        return ["打开官网资料", "确认新的资料形式", "补齐新的 PDF 或页面来源"]
    if status == "failed":
        return ["稍后重试检查", "如果连续失败，手动打开官网", "确认链接是否还能访问"]
    if status == "first_check":
        return ["打开官网来源", "确认学校、年度和留学生招生内容正确", "确认无误后接受来源凭据"]
    return ["打开来源", "判断是否需要复审"]


def _diff_preview(item: dict[str, Any]) -> dict[str, Any]:
    preview = item.get("diff_preview") if isinstance(item.get("diff_preview"), dict) else {}
    old_excerpt = [str(line) for line in preview.get("old_excerpt") or [] if str(line).strip()]
    new_excerpt = [str(line) for line in preview.get("new_excerpt") or [] if str(line).strip()]
    return {
        "old_excerpt": old_excerpt[:4],
        "new_excerpt": new_excerpt[:4],
        "has_text_comparison": bool(preview.get("has_text_comparison") or old_excerpt or new_excerpt),
    }


def _attention_level(status: str) -> str:
    if status == "changed":
        return "needs_review"
    if status in {"marker_mismatch", "not_pdf", "failed", "first_check"}:
        return "source_check"
    return "watch"


def build_change_report(queue: dict[str, Any], states: dict[str, Any] | None = None) -> dict[str, Any]:
    items = [item for item in queue.get("items") or [] if isinstance(item, dict)]
    state_map = states if states is not None else load_source_review_states()
    report_items = []
    for item in items:
        status = str(item.get("status") or "")
        item_id = source_review_item_id(item)
        state = state_map.get(item_id) if isinstance(state_map.get(item_id), dict) else {}
        review_status = str(state.get("review_status") or "open")
        report_items.append(
            {
                "item_id": item_id,
                "stem": item.get("stem", ""),
                "university": item.get("university", ""),
                "admission_year": item.get("admission_year", ""),
                "admission_type": item.get("admission_type", ""),
                "source_type": item.get("source_type", ""),
                "source_url": item.get("source_url", ""),
                "status": status,
                "old_sha256": item.get("old_sha256", ""),
                "new_sha256": item.get("new_sha256", ""),
                "checked_at": item.get("checked_at", ""),
                "error": item.get("error", ""),
                "missing_markers": item.get("missing_markers", []),
                "recommended_action": _action_for_status(status),
                "status_label": _status_label(status),
                "owner_summary": _owner_summary(item),
                "likely_changed_areas": _likely_changed_areas(item),
                "next_steps": _next_steps(item),
                "diff_preview": _diff_preview(item),
                "attention_level": _attention_level(status),
                "review_status": review_status,
                "review_note": state.get("note", ""),
                "review_updated_at": state.get("updated_at", ""),
                "data_update_status": "confirmed_records_unchanged",
                "safety_note": "来源变化只进入复审提醒；正式资料不会自动改动。",
                "confirmed_records_unchanged": True,
            }
        )
    summary = dict(queue.get("summary") or {})
    summary.setdefault("needs_review", len(report_items))
    summary["open"] = sum(1 for item in report_items if item.get("review_status") == "open")
    summary["reviewed"] = sum(1 for item in report_items if item.get("review_status") == "reviewed")
    summary["needs_reextract"] = sum(1 for item in report_items if item.get("review_status") == "needs_reextract")
    summary["deferred"] = sum(1 for item in report_items if item.get("review_status") == "deferred")
    return {
        "generated_at": queue.get("generated_at", ""),
        "summary": summary,
        "items": report_items,
        "confirmed_records_unchanged": True,
    }


def _short_hash(value: Any) -> str:
    text = str(value or "")
    return text[:12] if text else "-"


def format_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "# 官方来源变化复审报告",
        "",
        f"- 生成时间：{report.get('generated_at') or '-'}",
        f"- 待查看：{summary.get('needs_review', 0)}",
        f"- 官方资料有变化：{summary.get('changed', 0)}",
        f"- 新来源待确认：{summary.get('first_check', 0)}",
        f"- 检查失败：{summary.get('failed', 0)}",
        f"- 内容不匹配：{summary.get('marker_mismatch', 0)}",
        "",
        "这份报告只提醒人工复审，正式资料不会被自动改动。",
        "",
    ]
    items = report.get("items") if isinstance(report.get("items"), list) else []
    if not items:
        lines.append("暂时没有需要查看的来源变化。")
        return "\n".join(lines)

    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {index}. {item.get('university') or item.get('stem')}",
                "",
                f"- 年度：{item.get('admission_year') or '-'}",
                f"- 状态：{item.get('status_label') or item.get('status') or '-'}",
                f"- 摘要：{item.get('owner_summary') or '-'}",
                f"- 数据边界：{item.get('safety_note') or '正式资料不会自动改动。'}",
                f"- 先看：{', '.join(item.get('likely_changed_areas') or []) or '-'}",
                f"- 来源：{item.get('source_url') or '-'}",
                f"- 旧凭证：{_short_hash(item.get('old_sha256'))}",
                f"- 新凭证：{_short_hash(item.get('new_sha256'))}",
                f"- 建议：{item.get('recommended_action') or '-'}",
            ]
        )
        next_steps = item.get("next_steps") if isinstance(item.get("next_steps"), list) else []
        if next_steps:
            lines.append(f"- 下一步：{' -> '.join(str(step) for step in next_steps)}")
        if item.get("missing_markers"):
            lines.append(f"- 没找到的线索：{json.dumps(item.get('missing_markers'), ensure_ascii=False)}")
        diff_preview = item.get("diff_preview") if isinstance(item.get("diff_preview"), dict) else {}
        old_excerpt = [str(line) for line in diff_preview.get("old_excerpt") or [] if str(line).strip()]
        new_excerpt = [str(line) for line in diff_preview.get("new_excerpt") or [] if str(line).strip()]
        if old_excerpt or new_excerpt:
            lines.append("- 新旧片段：")
            for line in old_excerpt[:3]:
                lines.append(f"  - 以前：{line}")
            for line in new_excerpt[:3]:
                lines.append(f"  - 现在：{line}")
        if item.get("error"):
            lines.append(f"- 错误：{item.get('error')}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate a human-readable source change review report.")
    parser.add_argument("--queue", default="", help="Review queue JSON path. Defaults to data/source_review_queue.json.")
    parser.add_argument("--output", default="", help="Optional Markdown output path.")
    parser.add_argument("--json-output", default="", help="Optional JSON report output path.")
    args = parser.parse_args(argv)

    report = build_change_report(load_review_queue(path=Path(args.queue) if args.queue else None))
    markdown = format_markdown_report(report)
    if args.json_output:
        Path(args.json_output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.output:
        Path(args.output).write_text(markdown, encoding="utf-8")
    else:
        print(markdown)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
