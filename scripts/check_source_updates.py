from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.source_watchlist import build_source_watchlist  # noqa: E402


FetchResult = dict[str, Any]
Fetcher = Callable[[str], FetchResult]

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept": "application/pdf,text/html,application/xhtml+xml,*/*",
}


def content_sha256(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def fetch_source(url: str) -> FetchResult:
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=60)
    response.raise_for_status()
    return {
        "status_code": response.status_code,
        "content": response.content,
        "content_type": response.headers.get("content-type", ""),
        "final_url": response.url,
    }


def _html_text(content: bytes) -> str:
    text = content.decode("utf-8", errors="ignore")
    text = re.sub(r"<script\b[^<]*(?:(?!</script>)<[^<]*)*</script>", " ", text, flags=re.I)
    text = re.sub(r"<style\b[^<]*(?:(?!</style>)<[^<]*)*</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return " ".join(text.split())


def _pdf_probe_text(content: bytes) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "source.pdf"
        path.write_bytes(content)
        try:
            pages = extract_text_per_page(path)
            text = "\n".join(value for _page, value in sorted(pages.items()))
            if text.strip():
                return text
        except Exception:
            pass
    return content[:500_000].decode("utf-8", errors="ignore")


def _probe_text(source_type: str, content: bytes) -> str:
    if source_type == "pdf":
        return _pdf_probe_text(content)
    return _html_text(content)


def _marker_matches(text: str, marker: Any) -> bool:
    if isinstance(marker, list):
        return any(str(item) in text for item in marker if str(item).strip())
    return str(marker) in text


def _missing_markers(text: str, markers: list[Any]) -> list[Any]:
    return [marker for marker in markers if not _marker_matches(text, marker)]


def _status_for_check(item: dict[str, Any], content: bytes, content_type: str) -> tuple[str, dict[str, Any]]:
    source_type = str(item.get("source_type") or "unknown")
    if source_type == "pdf" and not content.startswith(b"%PDF-"):
        return "not_pdf", {"error": f"Expected PDF source but received content_type={content_type or 'unknown'}"}

    markers = list(item.get("markers") or [])
    if markers:
        text = _probe_text(source_type, content)
        missing = _missing_markers(text, markers)
        if missing:
            return "marker_mismatch", {"missing_markers": missing}

    new_hash = content_sha256(content)
    old_hash = str(item.get("last_known_sha256") or "")
    if old_hash and new_hash == old_hash:
        return "unchanged", {}
    if old_hash and new_hash != old_hash:
        return "changed", {}
    return "first_check", {}


def _check_one(item: dict[str, Any], *, fetcher: Fetcher, checked_at: str) -> dict[str, Any]:
    base = {
        "stem": item.get("stem", ""),
        "id": item.get("id", ""),
        "university": item.get("university", ""),
        "admission_year": item.get("admission_year", ""),
        "admission_type": item.get("admission_type", ""),
        "source_type": item.get("source_type", ""),
        "source_url": item.get("source_url", ""),
        "cached_path": item.get("cached_path", ""),
        "old_sha256": item.get("last_known_sha256", ""),
        "checked_at": checked_at,
        "confirmed_records_unchanged": True,
    }
    url = str(item.get("source_url") or "").strip()
    if not url:
        return {**base, "status": "failed", "error": "missing_source_url", "needs_review": True}
    try:
        fetched = fetcher(url)
        content = fetched.get("content") or b""
        if isinstance(content, str):
            content = content.encode("utf-8")
        content_type = str(fetched.get("content_type") or "")
        status, extra = _status_for_check(item, bytes(content), content_type)
        new_hash = content_sha256(bytes(content))
        return {
            **base,
            "status": status,
            "http_status": int(fetched.get("status_code") or 0),
            "content_type": content_type,
            "final_url": str(fetched.get("final_url") or url),
            "new_sha256": new_hash,
            "needs_review": status in {"changed", "failed", "marker_mismatch", "not_pdf"},
            **extra,
        }
    except Exception as exc:
        return {**base, "status": "failed", "error": str(exc), "needs_review": True}


def _write_jsonl(path: Path, items: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        for item in items:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def _review_queue(items: list[dict[str, Any]], *, checked_at: str) -> dict[str, Any]:
    review_items = [item for item in items if item.get("needs_review")]
    return {
        "generated_at": checked_at,
        "summary": {
            "needs_review": len(review_items),
            "changed": sum(1 for item in review_items if item.get("status") == "changed"),
            "failed": sum(1 for item in review_items if item.get("status") == "failed"),
            "marker_mismatch": sum(1 for item in review_items if item.get("status") == "marker_mismatch"),
            "not_pdf": sum(1 for item in review_items if item.get("status") == "not_pdf"),
        },
        "items": review_items,
    }


def _summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    statuses = ["unchanged", "changed", "failed", "marker_mismatch", "not_pdf", "first_check"]
    summary = {"total": len(items)}
    for status in statuses:
        summary[status] = sum(1 for item in items if item.get("status") == status)
    summary["needs_review"] = sum(1 for item in items if item.get("needs_review"))
    return summary


def check_watchlist_sources(
    *,
    watchlist: list[dict[str, Any]] | None = None,
    root: Path = ROOT,
    fetcher: Fetcher = fetch_source,
    output_path: Path | None = None,
    review_queue_path: Path | None = None,
    now: str | None = None,
    limit: int | None = None,
) -> dict[str, Any]:
    checked_at = now or _now_iso()
    sources = list(watchlist if watchlist is not None else build_source_watchlist(root=root))
    if limit is not None:
        sources = sources[: int(limit)]
    items = [_check_one(item, fetcher=fetcher, checked_at=checked_at) for item in sources]

    checks_path = output_path or root / "data" / "source_checks.jsonl"
    queue_path = review_queue_path or root / "data" / "source_review_queue.json"
    _write_jsonl(checks_path, items)
    queue = _review_queue(items, checked_at=checked_at)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_path.write_text(json.dumps(queue, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "checked_at": checked_at,
        "summary": _summary(items),
        "checks_path": str(checks_path),
        "review_queue_path": str(queue_path),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check official admissions sources for changes without updating confirmed records.")
    parser.add_argument("--output", default="", help="JSONL check log path. Defaults to data/source_checks.jsonl.")
    parser.add_argument("--review-queue", default="", help="Review queue path. Defaults to data/source_review_queue.json.")
    parser.add_argument("--report", default="", help="Optional JSON report path.")
    parser.add_argument("--limit", type=int, default=0, help="Optional max number of sources to check.")
    args = parser.parse_args(argv)

    report = check_watchlist_sources(
        output_path=Path(args.output) if args.output else None,
        review_queue_path=Path(args.review_queue) if args.review_queue else None,
        limit=args.limit or None,
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.report:
        Path(args.report).write_text(payload, encoding="utf-8")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
