from __future__ import annotations

import json
import argparse
import unicodedata
from pathlib import Path
from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def _normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", _text(value)).lower().split())


def _record_matches(expected_match: dict[str, Any], extracted: dict[str, Any]) -> bool:
    for field, expected_value in expected_match.items():
        if _normalize(extracted.get(field)) != _normalize(expected_value):
            return False
    return True


def _find_record(expected_match: dict[str, Any], extracted_records: list[dict[str, Any]]) -> dict[str, Any] | None:
    for record in extracted_records:
        if _record_matches(expected_match, record):
            return record
    return None


def _match_key(match_rule: dict[str, Any]) -> str:
    return json.dumps({str(key): _normalize(value) for key, value in sorted(match_rule.items())}, ensure_ascii=False, sort_keys=True)


def _baseline_integrity_failures(expected_records: list[dict[str, Any]]) -> list[dict[str, str]]:
    failures: list[dict[str, str]] = []
    seen_ids: dict[str, str] = {}
    seen_matches: dict[str, str] = {}
    for index, expected in enumerate(expected_records, start=1):
        expected_id = _text(expected.get("id")) or f"expected-{index}"
        if expected_id in seen_ids:
            failures.append({"id": expected_id, "failure": "duplicate_expected_id", "first_id": seen_ids[expected_id]})
        else:
            seen_ids[expected_id] = expected_id

        match_rule = expected.get("match") if isinstance(expected.get("match"), dict) else {}
        key = _match_key(match_rule)
        if key in seen_matches:
            failures.append({"id": expected_id, "failure": "duplicate_expected_match", "first_id": seen_matches[key]})
        else:
            seen_matches[key] = expected_id
    return failures


def _evaluate_value(field: str, expected_rule: Any, actual_value: Any) -> dict[str, Any]:
    actual = _text(actual_value)
    check = {
        "field": field,
        "expected": expected_rule,
        "actual": actual,
        "status": "passed",
    }

    if isinstance(expected_rule, dict):
        if expected_rule.get("optional") and not actual:
            check["status"] = "optional_empty"
            return check

        if "contains" in expected_rule:
            required = [_text(item) for item in expected_rule.get("contains") or [] if _text(item)]
            normalized_actual = _normalize(actual)
            missing = [item for item in required if _normalize(item) not in normalized_actual]
            if missing:
                check["status"] = "mismatch" if actual else "missing"
                check["missing_terms"] = missing
            return check

        if "any_of" in expected_rule:
            options = [_text(item) for item in expected_rule.get("any_of") or [] if _text(item)]
            normalized_actual = _normalize(actual)
            if not actual:
                check["status"] = "missing"
            elif not any(_normalize(option) in normalized_actual for option in options):
                check["status"] = "mismatch"
            return check

        expected_value = expected_rule.get("equals", "")
    else:
        expected_value = expected_rule

    expected = _text(expected_value)
    if not actual:
        check["status"] = "missing"
    elif _normalize(actual) != _normalize(expected):
        check["status"] = "mismatch"
    return check


def evaluate_against_expected(
    expected_records: list[dict[str, Any]],
    extracted_records: list[dict[str, Any]],
    *,
    min_exact_match_rate: float = 0.95,
    allow_extra_records: bool = False,
) -> dict[str, Any]:
    records: list[dict[str, Any]] = []
    matched_indexes: set[int] = set()
    checked_items = 0
    passed_items = 0
    missing_items = 0
    mismatched_items = 0
    optional_empty_items = 0
    unmatched_records = 0
    field_coverage: dict[str, dict[str, int]] = {}
    baseline_integrity_failures = _baseline_integrity_failures(expected_records)

    for expected in expected_records:
        expected_id = _text(expected.get("id")) or f"expected-{len(records) + 1}"
        match_rule = expected.get("match") if isinstance(expected.get("match"), dict) else {}
        expect_rule = expected.get("expect") if isinstance(expected.get("expect"), dict) else {}
        matched = None
        matched_index = -1
        for extracted_index, record in enumerate(extracted_records):
            if _record_matches(match_rule, record):
                matched = record
                matched_index = extracted_index
                break

        if matched is None:
            unmatched_records += 1
            records.append(
                {
                    "id": expected_id,
                    "match": match_rule,
                    "status": "unmatched",
                    "checks": [],
                }
            )
            continue
        matched_indexes.add(matched_index)

        checks = [_evaluate_value(field, rule, matched.get(field)) for field, rule in expect_rule.items()]
        for check in checks:
            field = str(check.get("field") or "")
            if field not in field_coverage:
                field_coverage[field] = {"checked": 0, "passed": 0, "missing": 0, "mismatched": 0, "optional_empty": 0}
            status = check["status"]
            if status == "optional_empty":
                field_coverage[field]["optional_empty"] += 1
                optional_empty_items += 1
                continue
            field_coverage[field]["checked"] += 1
            checked_items += 1
            if status == "passed":
                field_coverage[field]["passed"] += 1
                passed_items += 1
            elif status == "missing":
                field_coverage[field]["missing"] += 1
                missing_items += 1
            elif status == "mismatch":
                field_coverage[field]["mismatched"] += 1
                mismatched_items += 1

        record_status = "passed" if all(check["status"] in {"passed", "optional_empty"} for check in checks) else "failed"
        records.append(
            {
                "id": expected_id,
                "match": match_rule,
                "status": record_status,
                "checks": checks,
            }
        )

    exact_match_rate = round((passed_items / checked_items) if checked_items else 0.0, 4)
    unexpected_records = [
        record for index, record in enumerate(extracted_records) if index not in matched_indexes
    ]
    unexpected_count = len(unexpected_records)
    passed = (
        unmatched_records == 0
        and not baseline_integrity_failures
        and missing_items == 0
        and mismatched_items == 0
        and (allow_extra_records or unexpected_count == 0)
        and exact_match_rate >= min_exact_match_rate
    )
    return {
        "passed": passed,
        "expected_count": len(expected_records),
        "extracted_count": len(extracted_records),
        "matched_record_count": len(expected_records) - unmatched_records,
        "thresholds": {
            "min_exact_match_rate": min_exact_match_rate,
        },
        "summary": {
            "checked_items": checked_items,
            "passed_items": passed_items,
            "missing_items": missing_items,
            "mismatched_items": mismatched_items,
            "optional_empty_items": optional_empty_items,
            "unmatched_records": unmatched_records,
            "unexpected_records": unexpected_count,
            "duplicate_expected_ids": sum(1 for failure in baseline_integrity_failures if failure["failure"] == "duplicate_expected_id"),
            "duplicate_expected_matches": sum(1 for failure in baseline_integrity_failures if failure["failure"] == "duplicate_expected_match"),
            "exact_match_rate": exact_match_rate,
        },
        "baseline_integrity_failures": baseline_integrity_failures,
        "field_coverage": field_coverage,
        "unexpected_records": unexpected_records[:20],
        "records": records,
    }


def load_json_records(path: str | Path) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        records = payload.get("records")
        if isinstance(records, list):
            return [item for item in records if isinstance(item, dict)]
    return []


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Compare extracted admissions data against a human-reviewed baseline.")
    parser.add_argument("--expected", required=True, help="Path to expected baseline JSON.")
    parser.add_argument("--extracted", required=True, help="Path to extracted records JSON.")
    parser.add_argument("--output", default="", help="Optional path to write the JSON report.")
    parser.add_argument("--min-exact-match-rate", type=float, default=0.95)
    args = parser.parse_args(argv)

    report = evaluate_against_expected(
        load_json_records(args.expected),
        load_json_records(args.extracted),
        min_exact_match_rate=args.min_exact_match_rate,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
