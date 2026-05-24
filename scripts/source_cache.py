from __future__ import annotations

import argparse
import hashlib
import json
import shutil
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

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402


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


def import_checked_source(
    source_path: str | Path,
    *,
    stem: str,
    source_url: str,
    markers: list[Any],
    root: Path = ROOT,
) -> dict[str, Any]:
    source = Path(source_path)
    _ensure_pdf(source)

    text = _read_probe_text(source)
    missing = _missing_markers(text, markers)
    if missing:
        raise SourceCacheError("marker_mismatch: " + json.dumps(missing, ensure_ascii=False))

    upload_dir = root / "data" / "uploads"
    receipt_dir = root / "quality_sources"
    upload_dir.mkdir(parents=True, exist_ok=True)
    receipt_dir.mkdir(parents=True, exist_ok=True)

    cached = upload_dir / f"{stem}.pdf"
    shutil.copyfile(source, cached)
    receipt = {
        "status": "cached",
        "stem": stem,
        "source_url": source_url,
        "cached_path": f"data/uploads/{stem}.pdf",
        "sha256": _sha256(cached),
        "size_bytes": cached.stat().st_size,
        "markers": markers,
        "checked_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    }
    receipt_path = receipt_dir / f"{stem}.source.json"
    receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Import a manually downloaded official source PDF after marker checks.")
    parser.add_argument("--source", required=True, help="Path to the manually downloaded PDF.")
    parser.add_argument("--stem", required=True, help="Source stem, for example waseda_2027_official.")
    parser.add_argument("--source-url", required=True, help="Official source URL.")
    parser.add_argument("--marker", action="append", default=[], help="Required marker. Repeat for multiple required markers.")
    args = parser.parse_args(argv)

    try:
        receipt = import_checked_source(
            args.source,
            stem=args.stem,
            source_url=args.source_url,
            markers=list(args.marker),
        )
    except SourceCacheError as exc:
        print(json.dumps({"status": "rejected", "reason": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps(receipt, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
