from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.normalize_fields import EXCEL_COLUMNS, load_and_normalize  # noqa: E402


def export_tsv(input_path: Path, output_path: Path) -> dict[str, int | str]:
    normalized = load_and_normalize(input_path)
    records = normalized.get("records") or []
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.writer(fh, delimiter="\t", lineterminator="\n")
        writer.writerow(EXCEL_COLUMNS)
        for record in records:
            writer.writerow([record.get(column, "") for column in EXCEL_COLUMNS])
    return {"output": str(output_path), "records": len(records)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Export extracted admissions JSON to the standard TSV master schema.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = export_tsv(args.input, args.output)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
