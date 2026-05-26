from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.seed_registry import registered_seed_extractors  # noqa: E402

STALE_CHECK_DAYS = 30


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _receipt(root: Path, stem: str) -> dict[str, Any]:
    payload = _read_json(root / "quality_sources" / f"{stem}.source.json")
    return payload if isinstance(payload, dict) else {}


def _baseline_source_note(root: Path, stem: str) -> str:
    payload = _read_json(root / "quality_baselines" / f"{stem}.expected.json")
    if not isinstance(payload, list):
        return ""
    for record in payload:
        if isinstance(record, dict) and str(record.get("source_note") or "").strip():
            return str(record.get("source_note") or "").strip()
    return ""


def infer_source_type(source_url: str, seed: dict[str, Any] | None = None) -> str:
    explicit = str((seed or {}).get("source_type") or "").strip().lower()
    if explicit:
        return explicit
    candidates = " ".join(str(item).lower() for item in (seed or {}).get("source_candidates") or [])
    if ".pdf" in candidates:
        return "pdf"
    lowered = source_url.lower()
    if ".pdf" in lowered or "@@download" in lowered or "download.html" in lowered:
        return "pdf"
    if lowered.startswith(("http://", "https://")):
        return "html"
    if lowered:
        return "cached_text"
    return "unknown"


def infer_admission_type(stem: str, seed: dict[str, Any] | None = None) -> str:
    explicit = str((seed or {}).get("admission_type") or "").strip()
    if explicit:
        return explicit
    lowered = stem.lower()
    if "medicine" in lowered:
        return "international_medicine"
    if "undergrad" in lowered or "official" in lowered or "schedule" in lowered:
        return "international_undergraduate"
    return "international_student_admissions"


def _source_note(root: Path, stem: str, seed: dict[str, Any]) -> str:
    return (
        str(seed.get("source_note") or "").strip()
        or _baseline_source_note(root, stem)
        or "Official university admissions source for international student admissions."
    )


def build_source_watchlist(
    *,
    root: Path = ROOT,
    seeds: dict[str, dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    seed_map = seeds if seeds is not None else registered_seed_extractors()
    items: list[dict[str, Any]] = []
    for seed_key, seed in sorted(seed_map.items()):
        stem = str(seed.get("stem") or seed_key)
        receipt = _receipt(root, stem)
        source_url = str(seed.get("source_url") or receipt.get("source_url") or "").strip()
        candidates = [str(item) for item in seed.get("source_candidates") or []]
        cached_path = str(receipt.get("cached_path") or (candidates[0] if candidates else "")).strip()
        items.append(
            {
                "stem": stem,
                "id": str(seed.get("id") or stem),
                "university": str(seed.get("university") or ""),
                "admission_year": str(seed.get("admission_year") or ""),
                "admission_type": infer_admission_type(stem, seed),
                "source_type": infer_source_type(source_url, seed),
                "source_url": source_url,
                "cached_path": cached_path,
                "source_candidates": candidates,
                "last_known_sha256": str(receipt.get("sha256") or "").strip(),
                "last_checked_at": str(receipt.get("checked_at") or "").strip(),
                "source_note": _source_note(root, stem, seed),
                "markers": list(seed.get("source_markers") or []),
                "receipt_status": str(receipt.get("status") or ""),
            }
        )
    return items


def _parse_checked_at(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def summarize_watchlist(
    items: list[dict[str, Any]],
    *,
    now: datetime | None = None,
    stale_days: int = STALE_CHECK_DAYS,
) -> dict[str, Any]:
    by_type: dict[str, int] = {}
    now_utc = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    stale_cutoff = now_utc.timestamp() - max(1, int(stale_days)) * 24 * 60 * 60
    gaps = {
        "missing_source_url": 0,
        "missing_source_type": 0,
        "missing_hash": 0,
        "missing_last_checked_at": 0,
        "missing_source_note": 0,
        "stale_last_checked_at": 0,
    }
    oldest_checked_at = ""
    for item in items:
        source_type = str(item.get("source_type") or "unknown")
        by_type[source_type] = by_type.get(source_type, 0) + 1
        if not str(item.get("source_url") or "").strip():
            gaps["missing_source_url"] += 1
        if source_type == "unknown":
            gaps["missing_source_type"] += 1
        if not str(item.get("last_known_sha256") or "").strip():
            gaps["missing_hash"] += 1
        checked_at = _parse_checked_at(item.get("last_checked_at"))
        if not checked_at:
            gaps["missing_last_checked_at"] += 1
        else:
            if checked_at.timestamp() < stale_cutoff:
                gaps["stale_last_checked_at"] += 1
            if not oldest_checked_at or checked_at.isoformat() < oldest_checked_at:
                oldest_checked_at = checked_at.isoformat()
        if not str(item.get("source_note") or "").strip():
            gaps["missing_source_note"] += 1
    return {
        "total": len(items),
        "by_type": by_type,
        "metadata_gaps": gaps,
        "stale_check_days": stale_days,
        "oldest_checked_at": oldest_checked_at,
    }


def build_watchlist_report(*, root: Path = ROOT) -> dict[str, Any]:
    items = build_source_watchlist(root=root)
    return {"summary": summarize_watchlist(items), "items": items}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build the official admissions source watchlist.")
    parser.add_argument("--output", default="", help="Optional JSON output path.")
    parser.add_argument("--summary", action="store_true", help="Print a compact summary instead of JSON.")
    args = parser.parse_args(argv)

    report = build_watchlist_report()
    if args.summary:
        summary = report["summary"]
        gaps = summary["metadata_gaps"]
        payload = "\n".join(
            [
                f"watched sources: {summary['total']}",
                "source types: " + ", ".join(f"{key}={value}" for key, value in sorted(summary["by_type"].items())),
                "metadata gaps: " + ", ".join(f"{key}={value}" for key, value in sorted(gaps.items())),
            ]
        )
    else:
        payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
