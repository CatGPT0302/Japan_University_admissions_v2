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

from scripts.quality_baseline import load_json_records  # noqa: E402


REGISTERED_SEED_EXTRACTORS = {
    "meiji_2027_schedule": {
        "script": "scripts/meiji_schedule_extractor.py",
        "source_candidates": ["data/uploads/meiji_2027_schedule_official.pdf"],
    }
}


def _local_source_exists(root: Path, stem: str, registration: dict[str, Any] | None) -> bool:
    candidates = []
    if registration:
        candidates.extend(str(item) for item in registration.get("source_candidates") or [])
    candidates.extend(
        [
            f"data/uploads/{stem}_official.pdf",
            f"data/uploads/{stem}.pdf",
            f"input_pdfs/{stem}.pdf",
        ]
    )
    return any((root / candidate).exists() and (root / candidate).stat().st_size > 0 for candidate in candidates)


def _record_count(records: list[dict[str, Any]], review_status: str) -> int:
    return sum(1 for record in records if record.get("review_status") == review_status)


def _status(*, has_source: bool, has_extractor: bool, human_checked: int) -> str:
    if human_checked <= 0:
        return "baseline_needs_human_check"
    if has_source and has_extractor:
        return "covered_by_seed_suite"
    if not has_source and not has_extractor:
        return "needs_source_and_extractor"
    if not has_source:
        return "needs_local_source"
    return "needs_seed_extractor"


def _next_actions(status: str) -> list[str]:
    mapping = {
        "baseline_needs_human_check": ["human_check_baseline_records"],
        "covered_by_seed_suite": ["expand_checked_rows_when_ready"],
        "needs_source_and_extractor": ["add_local_source_pdf", "add_seed_extractor_or_pipeline_fixture"],
        "needs_local_source": ["add_local_source_pdf"],
        "needs_seed_extractor": ["add_seed_extractor_or_pipeline_fixture"],
    }
    return list(mapping.get(status, []))


def _todo_details(stem: str, action: str) -> str:
    if action == "add_local_source_pdf":
        candidates = [f"data/uploads/{stem}.pdf"]
        if not stem.endswith("_official"):
            candidates.append(f"data/uploads/{stem}_official.pdf")
        return "Place the checked source PDF at " + " or ".join(candidates) + "."
    if action == "add_seed_extractor_or_pipeline_fixture":
        return "Add a deterministic seed extractor or a pipeline fixture, then register it in scripts/quality_gap_report.py and scripts/quality_baseline_suite.py."
    if action == "human_check_baseline_records":
        return "Check every expected value against the source document and set review_status to human_checked_seed."
    return "No immediate blocking action; extend checked rows when more source rows have been reviewed."


def _build_owner_todo(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    priority = {
        "add_local_source_pdf": 10,
        "human_check_baseline_records": 20,
        "add_seed_extractor_or_pipeline_fixture": 30,
        "expand_checked_rows_when_ready": 90,
    }
    todos: list[dict[str, Any]] = []
    for item in items:
        for action in item.get("next_actions") or []:
            if action == "expand_checked_rows_when_ready":
                continue
            todos.append(
                {
                    "priority": priority.get(str(action), 50),
                    "baseline": item["stem"],
                    "action": action,
                    "details": _todo_details(str(item["stem"]), str(action)),
                }
            )
    return sorted(todos, key=lambda todo: (int(todo["priority"]), str(todo["baseline"]), str(todo["action"])))


def build_quality_gap_report(*, root: Path = ROOT) -> dict[str, Any]:
    baseline_dir = root / "quality_baselines"
    items: list[dict[str, Any]] = []

    for path in sorted(baseline_dir.glob("*.expected.json")):
        stem = path.name.removesuffix(".expected.json")
        records = load_json_records(path)
        human_checked = _record_count(records, "human_checked_seed")
        draft = _record_count(records, "draft_needs_human_check")
        registration = REGISTERED_SEED_EXTRACTORS.get(stem)
        has_extractor = bool(registration)
        has_source = _local_source_exists(root, stem, registration)
        status = _status(has_source=has_source, has_extractor=has_extractor, human_checked=human_checked)
        items.append(
            {
                "stem": stem,
                "baseline_path": str(path),
                "expected_records": len(records),
                "human_checked_records": human_checked,
                "draft_records": draft,
                "local_source_available": has_source,
                "registered_seed_extractor": has_extractor,
                "status": status,
                "next_actions": _next_actions(status),
            }
        )

    return {
        "summary": {
            "baseline_files": len(items),
            "expected_records": sum(int(item["expected_records"]) for item in items),
            "human_checked_records": sum(int(item["human_checked_records"]) for item in items),
            "registered_seed_extractors": sum(1 for item in items if item["registered_seed_extractor"]),
            "missing_local_sources": sum(1 for item in items if not item["local_source_available"]),
            "missing_seed_extractors": sum(1 for item in items if not item["registered_seed_extractor"]),
        },
        "baseline_files": items,
        "owner_todo": _build_owner_todo(items),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Report extraction-quality baseline coverage gaps and next actions.")
    parser.add_argument("--output", default="", help="Optional path to write JSON report.")
    args = parser.parse_args(argv)

    report = build_quality_gap_report()
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
