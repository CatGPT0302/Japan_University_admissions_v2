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

from scripts.seed_registry import registered_seed_extractors  # noqa: E402
from scripts.source_cache import download_checked_source  # noqa: E402


def _first_existing_source(root: Path, candidates: list[str]) -> Path | None:
    for candidate in candidates:
        path = root / candidate
        if path.exists() and path.stat().st_size > 0:
            return path
    return None


def sync_registered_sources(
    *,
    registry: dict[str, dict[str, Any]] | None = None,
    root: Path = ROOT,
    only_stem: str = "",
    verify_overview: bool = False,
) -> dict[str, Any]:
    seeds = registry if registry is not None else registered_seed_extractors()
    report: dict[str, Any] = {
        "downloaded": [],
        "skipped_existing": [],
        "skipped_unconfigured": [],
    }

    for key, seed in seeds.items():
        stem = str(seed.get("stem") or key)
        if only_stem and stem != only_stem:
            continue

        candidates = [str(item) for item in seed.get("source_candidates") or []]
        if _first_existing_source(root, candidates):
            report["skipped_existing"].append(stem)
            continue

        source_url = str(seed.get("source_url") or "")
        markers = list(seed.get("source_markers") or [])
        if not source_url or not markers:
            report["skipped_unconfigured"].append(stem)
            continue

        download_checked_source(
            source_url=source_url,
            stem=stem,
            markers=markers,
            root=root,
            verify_overview=verify_overview,
        )
        report["downloaded"].append(stem)

    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Download missing registered quality source PDFs.")
    parser.add_argument("--stem", default="", help="Optional single source stem to sync.")
    parser.add_argument("--verify-overview", action="store_true", help="Include quality overview after each downloaded source.")
    args = parser.parse_args(argv)

    report = sync_registered_sources(only_stem=args.stem, verify_overview=args.verify_overview)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
