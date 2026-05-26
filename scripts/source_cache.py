from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.quality_overview import build_quality_overview, format_owner_summary  # noqa: E402
from scripts.seed_registry import registered_seed_extractors  # noqa: E402


BROWSER_DOWNLOAD_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125 Safari/537.36",
    "Accept": "application/pdf,application/octet-stream,*/*",
}


class SourceCacheError(ValueError):
    pass


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_probe_text(path: Path) -> str:
    try:
        pages = extract_text_per_page(path)
        text = "\n".join(str(value or "") for _page, value in sorted(pages.items()))
        if text.strip():
            return text
    except Exception:
        pass
    return path.read_bytes()[:500_000].decode("utf-8", errors="ignore")


def _marker_matches(text: str, marker: Any) -> bool:
    if isinstance(marker, list):
        return any(str(item) in text for item in marker if str(item).strip())
    return str(marker) in text


def _missing_markers(text: str, markers: list[Any]) -> list[Any]:
    return [marker for marker in markers if not _marker_matches(text, marker)]


def _ensure_pdf(path: Path) -> None:
    if not path.exists() or not path.is_file():
        raise SourceCacheError("missing_source")
    with path.open("rb") as handle:
        header = handle.read(5)
    if header != b"%PDF-":
        raise SourceCacheError("not_pdf")


def _canonical_cached_path(root: Path, stem: str) -> Path:
    seed = registered_seed_extractors().get(stem) or {}
    candidates = list(seed.get("source_candidates") or [])
    if candidates:
        return root / str(candidates[0])
    return root / "data" / "uploads" / f"{stem}.pdf"


def import_checked_source(
    source_path: str | Path,
    *,
    stem: str,
    source_url: str,
    markers: list[Any],
    root: Path = ROOT,
    verify_overview: bool = False,
) -> dict[str, Any]:
    source = Path(source_path)
    _ensure_pdf(source)

    text = _read_probe_text(source)
    missing = _missing_markers(text, markers)
    if missing:
        raise SourceCacheError("marker_mismatch: " + json.dumps(missing, ensure_ascii=False))

    receipt_dir = root / "quality_sources"
    receipt_dir.mkdir(parents=True, exist_ok=True)

    cached = _canonical_cached_path(root, stem)
    cached.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, cached)
    cached_path = cached.relative_to(root).as_posix()
    receipt = {
        "status": "cached",
        "stem": stem,
        "source_url": source_url,
        "cached_path": cached_path,
        "sha256": _sha256(cached),
        "size_bytes": cached.stat().st_size,
        "markers": markers,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    receipt_path = receipt_dir / f"{stem}.source.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")

    if verify_overview:
        overview = build_quality_overview()
        receipt["quality_overview_status"] = str(overview.get("overall_status", "unknown"))
        receipt["quality_overview_summary"] = format_owner_summary(overview)

    return receipt


def download_checked_source(
    *,
    source_url: str,
    stem: str,
    markers: list[Any],
    root: Path = ROOT,
    verify_overview: bool = False,
) -> dict[str, Any]:
    headers = dict(BROWSER_DOWNLOAD_HEADERS)
    headers["Referer"] = source_url.rsplit("/", 1)[0] + "/"
    response = requests.get(source_url, headers=headers, timeout=60)
    response.raise_for_status()
    with tempfile.TemporaryDirectory() as tmp:
        downloaded = Path(tmp) / f"{stem}.pdf"
        downloaded.write_bytes(response.content)
        return import_checked_source(
            downloaded,
            stem=stem,
            source_url=source_url,
            markers=markers,
            root=root,
            verify_overview=verify_overview,
        )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a manually downloaded official source PDF after marker checks.")
    parser.add_argument("--source", default="", help="Path to the manually downloaded PDF.")
    parser.add_argument("--stem", required=True, help="Source stem, for example waseda_2027_official.")
    parser.add_argument("--source-url", required=True, help="Official source URL.")
    parser.add_argument("--marker", action="append", default=[], help="Required marker. Repeat for multiple required markers.")
    parser.add_argument("--download", action="store_true", help="Download the official source URL before marker checks.")
    parser.add_argument(
        "--verify-overview",
        action="store_true",
        help="Run the quality overview after import and include the summary in the command output.",
    )
    args = parser.parse_args(argv)

    try:
        if args.download:
            receipt = download_checked_source(
                source_url=args.source_url,
                stem=args.stem,
                markers=list(args.marker),
                verify_overview=args.verify_overview,
            )
        else:
            if not args.source:
                raise SourceCacheError("missing_source")
            receipt = import_checked_source(
                args.source,
                stem=args.stem,
                source_url=args.source_url,
                markers=list(args.marker),
                verify_overview=args.verify_overview,
            )
    except SourceCacheError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
