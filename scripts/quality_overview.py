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


def _overall_status(seed_suite: dict[str, Any], gap_report: dict[str, Any]) -> str:
    if not seed_suite.get("passed"):
        return "seed_suite_failed"
    if gap_report.get("owner_todo"):
        return "needs_owner_action"
    return "quality_gate_ready"


def build_quality_overview() -> dict[str, Any]:
    seed_suite = run_seed_baseline_suite()
    gap_report = build_quality_gap_report()
    owner_todo = gap_report.get("owner_todo") if isinstance(gap_report.get("owner_todo"), list) else []
    return {
        "overall_status": _overall_status(seed_suite, gap_report),
        "seed_suite": seed_suite,
        "gap_report": gap_report,
        "next_owner_action": owner_todo[0] if owner_todo else None,
    }


def format_owner_summary(overview: dict[str, Any]) -> str:
    seed_summary = overview.get("seed_suite", {}).get("summary", {})
    gap_summary = overview.get("gap_report", {}).get("summary", {})
    next_action = overview.get("next_owner_action") if isinstance(overview.get("next_owner_action"), dict) else None
    lines = [
        f"status: {overview.get('overall_status')}",
        f"seed suite: {seed_summary.get('passed', 0)}/{seed_summary.get('total', 0)} passed",
        f"baseline files: {gap_summary.get('baseline_files', 0)}",
        f"missing local sources: {gap_summary.get('missing_local_sources', 0)}",
        f"missing seed extractors: {gap_summary.get('missing_seed_extractors', 0)}",
    ]
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

    overview = build_quality_overview()
    payload = format_owner_summary(overview) if args.summary else json.dumps(overview, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0 if overview["overall_status"] != "seed_suite_failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
