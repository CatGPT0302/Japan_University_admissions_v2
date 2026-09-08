from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.quality_baseline import load_json_records


IDENTITY_FIELDS = ["university", "admission_year", "faculty", "department"]
VALUE_FIELDS = {
    "application_period": ["application_period"],
    "deadline_rule": ["deadline_rule", "deadline"],
    "eju_session": ["eju_session"],
    "eju_subjects": ["eju_subjects"],
    "english_requirement": ["english_requirement"],
    "screening_method": ["screening_method"],
    "screening_schedule": ["screening_schedule"],
    "result_date": ["result_date"],
    "enrollment_period": ["enrollment_period"],
}
UNIVERSITY_SLUGS = {
    "明治大学": "meiji",
    "早稲田大学": "waseda",
    "中央大学": "chuo",
    "立教大学": "rikkyo",
    "慶應義塾大学": "keio",
}


def _text(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str) -> str:
    if value in UNIVERSITY_SLUGS:
        return UNIVERSITY_SLUGS[value]
    ascii_slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if ascii_slug:
        return ascii_slug
    return "baseline"


def _first_value(record: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        value = _text(record.get(key))
        if value:
            return value
    return ""


def _contains_rule(value: str) -> dict[str, list[str]]:
    terms = [part.strip() for part in re.split(r"[、,，/／]+", value) if part.strip()]
    return {"contains": terms} if len(terms) > 1 else {"contains": [value]}


def build_baseline_draft(records: list[dict[str, Any]], *, max_records: int | None = None) -> list[dict[str, Any]]:
    draft: list[dict[str, Any]] = []
    for record in records:
        match = {field: _text(record.get(field)) for field in IDENTITY_FIELDS}
        if not all(match.values()):
            continue

        expect: dict[str, Any] = {}
        for target, source_keys in VALUE_FIELDS.items():
            value = _first_value(record, source_keys)
            if not value:
                continue
            expect[target] = _contains_rule(value) if target == "eju_subjects" else value

        if not expect:
            continue

        university_slug = _slug(match["university"])
        draft.append(
            {
                "id": f"{university_slug}-{match['admission_year']}-{len(draft) + 1:03d}",
                "match": match,
                "expect": expect,
                "review_status": "draft_needs_human_check",
            }
        )
        if max_records is not None and len(draft) >= max_records:
            break
    return draft


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a human-review draft baseline from extracted records.")
    parser.add_argument("--input", required=True, help="Extracted records JSON or JSONL-like JSON payload.")
    parser.add_argument("--output", required=True, help="Path to write draft expected baseline JSON.")
    parser.add_argument("--max-records", type=int, default=0)
    args = parser.parse_args(argv)

    records = load_json_records(args.input)
    draft = build_baseline_draft(records, max_records=args.max_records or None)
    Path(args.output).write_text(json.dumps(draft, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
