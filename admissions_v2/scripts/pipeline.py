"""
Deprecated wrapper around the unified OpenAI extraction backend.

This file is kept for backward compatibility with old commands:
    python scripts/pipeline.py --pdf input_pdfs/meiji.pdf --university 明治大学 --year 2026

Internally it now delegates to scripts.extract_direct.run_extraction().
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import extract_direct  # noqa: E402


def run_pipeline(
    pdf_path: Path,
    university: str,
    admission_year: str,
    pdf_url: str = "",
    pages: list[int] | None = None,
    dpi: int = 200,
    hsplit_pages: set[int] | None = None,
) -> dict[str, Any]:
    if pages or hsplit_pages:
        print("[pipeline] note: --pages/--hsplit are deprecated and ignored in OpenAI-only mode.")
    if dpi != 200:
        print("[pipeline] note: --dpi is deprecated and ignored in OpenAI-only mode.")

    result = extract_direct.run_extraction(
        pdf_path=pdf_path,
        university=university,
        year=str(admission_year),
        url=pdf_url or "",
    )
    return {
        "doc_id": result.get("doc_id"),
        "status": result.get("status"),
        "mode": result.get("mode"),
        "pages_processed": result.get("pages"),
        "total_records": result.get("records"),
        "inserted": result.get("inserted"),
        "failed_pages": result.get("failed_pages", []),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--university", required=True)
    parser.add_argument("--year", default="")
    parser.add_argument("--url", default="")
    parser.add_argument("--pages", nargs="*", type=int)
    parser.add_argument("--hsplit", nargs="*", type=int, help="Deprecated: ignored in OpenAI-only mode")
    parser.add_argument("--dpi", type=int, default=200, help="Deprecated: ignored in OpenAI-only mode")
    args = parser.parse_args()

    result = run_pipeline(
        pdf_path=Path(args.pdf),
        university=args.university,
        admission_year=args.year,
        pdf_url=args.url,
        pages=args.pages,
        dpi=args.dpi,
        hsplit_pages=set(args.hsplit) if args.hsplit else None,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
