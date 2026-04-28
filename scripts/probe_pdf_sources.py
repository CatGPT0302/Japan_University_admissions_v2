from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.fetch_pdfs import probe_targets


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Probe maintained university target pages and report possible new PDF links."
    )
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument(
        "--save-json",
        default="",
        help="Optional output path for JSON report.",
    )
    args = parser.parse_args()

    report = probe_targets(year=args.year)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    print(payload)

    save_path = str(args.save_json or "").strip()
    if save_path:
        target = Path(save_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(payload, encoding="utf-8")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
