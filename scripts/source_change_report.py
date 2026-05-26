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
        return "source changed; compare the official source and decide whether extraction or confirmed records need updating"
    if status == "marker_mismatch":
        return "source downloaded but expected school/admissions markers were not found; verify URL before using it"
    if status == "not_pdf":
        return "source was expected to be a PDF but did not look like one; verify whether the university changed the link"
    if status == "failed":
        return "source check failed; retry later or open the official URL manually"
    return "review source status"


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
                "source_url": item.get("source_url", ""),
                "status": status,
                "old_sha256": item.get("old_sha256", ""),
                "new_sha256": item.get("new_sha256", ""),
                "checked_at": item.get("checked_at", ""),
                "error": item.get("error", ""),
                "missing_markers": item.get("missing_markers", []),
                "recommended_action": _action_for_status(status),
                "review_status": review_status,
                "review_note": state.get("note", ""),
                "review_updated_at": state.get("updated_at", ""),
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
        "# Source Change Review",
        "",
        f"- Generated at: {report.get('generated_at') or '-'}",
        f"- Items needing review: {summary.get('needs_review', 0)}",
        f"- Changed sources: {summary.get('changed', 0)}",
        f"- Failed checks: {summary.get('failed', 0)}",
        f"- Marker mismatches: {summary.get('marker_mismatch', 0)}",
        "",
        "confirmed records were not changed by this report.",
        "",
    ]
    items = report.get("items") if isinstance(report.get("items"), list) else []
    if not items:
        lines.append("No source review items.")
        return "\n".join(lines)

    for index, item in enumerate(items, start=1):
        lines.extend(
            [
                f"## {index}. {item.get('university') or item.get('stem')}",
                "",
                f"- Year: {item.get('admission_year') or '-'}",
                f"- Status: {item.get('status') or '-'}",
                f"- Source: {item.get('source_url') or '-'}",
                f"- Old hash: {_short_hash(item.get('old_sha256'))}",
                f"- New hash: {_short_hash(item.get('new_sha256'))}",
                f"- Recommendation: {item.get('recommended_action') or '-'}",
            ]
        )
        if item.get("missing_markers"):
            lines.append(f"- Missing markers: {json.dumps(item.get('missing_markers'), ensure_ascii=False)}")
        if item.get("error"):
            lines.append(f"- Error: {item.get('error')}")
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
