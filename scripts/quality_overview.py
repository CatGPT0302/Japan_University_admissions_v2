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

from scripts.quality_baseline_suite import run_seed_baseline_suite  # noqa: E402
from scripts.quality_gap_report import build_quality_gap_report  # noqa: E402
from scripts.source_text_health import audit_seed_source_text_layers  # noqa: E402


CRITICAL_FIELD_MINIMUMS = {
    "application_period": 5,
    "deadline_rule": 5,
    "enrollment_period": 5,
    "required_documents": 5,
    "eligibility": 5,
    "evidence": 5,
    "eju_session": 5,
    "eju_japanese": 5,
    "eju_general": 5,
    "eju_math": 2,
    "eju_physics": 1,
    "eju_chemistry": 1,
    "english_requirement": 5,
    "result_date": 5,
    "screening_schedule": 5,
}

SEED_RECORD_MINIMUMS = {
    "meiji-2027-schedule": 12,
    "waseda-2027-official": 12,
    "keio-2027-medicine": 1,
    "kwansei-2027-undergrad": 3,
    "kindai-2027-undergrad": 3,
    "ritsumeikan-2027-undergrad": 3,
    "osaka-metropolitan-2027-undergrad": 3,
    "chukyo-gakuin-2027-undergrad": 2,
    "kit-2027-undergrad": 4,
}


def _overall_status(seed_suite: dict[str, Any], gap_report: dict[str, Any]) -> str:
    if not seed_suite.get("passed"):
        return "seed_suite_failed"
    if gap_report.get("owner_todo"):
        return "needs_owner_action"
    return "quality_gate_ready"


def build_quality_overview(*, include_source_text_health: bool = False) -> dict[str, Any]:
    seed_suite = run_seed_baseline_suite()
    gap_report = build_quality_gap_report()
    gap_todo = gap_report.get("owner_todo") if isinstance(gap_report.get("owner_todo"), list) else []
    quality_todo = _seed_record_todos(seed_suite) + _critical_field_todos(seed_suite) + _weak_field_todos(seed_suite)
    owner_todo = gap_todo + quality_todo
    overview = {
        "overall_status": "seed_suite_failed" if not seed_suite.get("passed") else ("needs_owner_action" if owner_todo else "quality_gate_ready"),
        "seed_suite": seed_suite,
        "gap_report": gap_report,
        "quality_todo": quality_todo,
        "owner_todo": owner_todo,
        "next_owner_action": owner_todo[0] if owner_todo else None,
    }
    if include_source_text_health:
        overview["source_text_health"] = audit_seed_source_text_layers()
    return overview


def _field_coverage_totals(seed_suite: dict[str, Any]) -> dict[str, int]:
    totals: dict[str, int] = {}
    for item in seed_suite.get("items") or []:
        baseline = item.get("baseline") if isinstance(item, dict) else {}
        coverage = baseline.get("field_coverage") if isinstance(baseline, dict) else {}
        if not isinstance(coverage, dict):
            continue
        for field, stats in coverage.items():
            if isinstance(stats, dict):
                totals[str(field)] = totals.get(str(field), 0) + int(stats.get("checked") or 0)
    return totals


def _weak_field_rows(seed_suite: dict[str, Any], *, max_checked: int = 2) -> list[dict[str, Any]]:
    totals = _field_coverage_totals(seed_suite)
    weak = [
        (field, checked)
        for field, checked in totals.items()
        if field in CRITICAL_FIELD_MINIMUMS and checked <= max_checked and checked < int(CRITICAL_FIELD_MINIMUMS[field])
    ]
    return [{"field": field, "checked": checked} for field, checked in sorted(weak, key=lambda item: (item[1], item[0]))[:5]]


def _weak_field_coverage(seed_suite: dict[str, Any], *, max_checked: int = 2) -> list[str]:
    return [f"{item['field']} checked={item['checked']}" for item in _weak_field_rows(seed_suite, max_checked=max_checked)]


def _weak_field_todos(seed_suite: dict[str, Any]) -> list[dict[str, Any]]:
    todos = []
    for item in _weak_field_rows(seed_suite):
        todos.append(
            {
                "priority": 80,
                "action": "expand_field_baseline",
                "field": item["field"],
                "checked": item["checked"],
                "details": f"Add more human-checked baseline expectations for {item['field']}.",
            }
        )
    return todos


def _critical_field_todos(seed_suite: dict[str, Any]) -> list[dict[str, Any]]:
    totals = _field_coverage_totals(seed_suite)
    todos = []
    for field, minimum in CRITICAL_FIELD_MINIMUMS.items():
        checked = int(totals.get(field) or 0)
        if checked < minimum:
            todos.append(
                {
                    "priority": 40,
                    "action": "critical_field_coverage_below_target",
                    "field": field,
                    "checked": checked,
                    "minimum": minimum,
                    "details": f"Add human-checked baseline expectations for {field} until at least {minimum} records are covered.",
                }
            )
    return todos


def _seed_record_todos(seed_suite: dict[str, Any]) -> list[dict[str, Any]]:
    todos = []
    for item in seed_suite.get("items") or []:
        if not isinstance(item, dict):
            continue
        seed_id = str(item.get("id") or "")
        minimum = SEED_RECORD_MINIMUMS.get(seed_id)
        if minimum is None:
            continue
        baseline = item.get("baseline") if isinstance(item.get("baseline"), dict) else {}
        if "expected_count" not in baseline:
            continue
        checked = int(baseline.get("expected_count") or 0)
        if checked < minimum:
            todos.append(
                {
                    "priority": 35,
                    "action": "seed_record_count_below_target",
                    "seed": seed_id,
                    "checked": checked,
                    "minimum": minimum,
                    "details": f"Add human-checked seed records for {seed_id} until at least {minimum} records are covered.",
                }
            )
    return todos


def format_owner_summary(overview: dict[str, Any]) -> str:
    seed_summary = overview.get("seed_suite", {}).get("summary", {})
    gap_summary = overview.get("gap_report", {}).get("summary", {})
    next_action = overview.get("next_owner_action") if isinstance(overview.get("next_owner_action"), dict) else None
    seed_line = f"seed suite: {seed_summary.get('passed', 0)}/{seed_summary.get('total', 0)} passed"
    if int(seed_summary.get("skipped") or 0):
        seed_line += f", {seed_summary.get('skipped')} skipped"
    lines = [
        f"status: {overview.get('overall_status')}",
        seed_line,
        f"baseline files: {gap_summary.get('baseline_files', 0)}",
        f"registered extractors: {gap_summary.get('registered_seed_extractors', 0)}",
        f"missing local sources: {gap_summary.get('missing_local_sources', 0)}",
        f"missing seed extractors: {gap_summary.get('missing_seed_extractors', 0)}",
    ]
    source_health = overview.get("source_text_health") if isinstance(overview.get("source_text_health"), dict) else {}
    source_summary = source_health.get("summary") if isinstance(source_health.get("summary"), dict) else {}
    if source_summary:
        lines.append(f"source text checks: {source_summary.get('manual_text_check_needed', 0)} need manual/vision review")
    weak_fields = _weak_field_coverage(overview.get("seed_suite", {}))
    if weak_fields:
        lines.append("weak field coverage: " + "; ".join(weak_fields))
    if next_action:
        lines.append(f"next: {next_action.get('baseline')} -> {next_action.get('action')}")
        lines.append(f"details: {next_action.get('details')}")
    else:
        lines.append("next: expand checked rows when ready")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run extraction quality overview: seed gates, coverage gaps, and owner todo.")
    parser.add_argument("--output", default="", help="Optional path to write JSON report.")
    parser.add_argument("--summary", action="store_true", help="Print a compact owner-readable summary instead of JSON.")
    args = parser.parse_args(argv)

    overview = build_quality_overview(include_source_text_health=args.summary)
    payload = format_owner_summary(overview) if args.summary else json.dumps(overview, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0 if overview["overall_status"] != "seed_suite_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
