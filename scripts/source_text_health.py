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

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.seed_registry import registered_seed_extractors  # noqa: E402


JAPANESE_TERMS = (
    "外国人留学生",
    "留学生",
    "入学試験",
    "募集要項",
    "出願",
    "試験",
    "日本留学試験",
    "合格",
    "英語",
    "書類",
)


def _is_common_japanese_char(char: str) -> bool:
    code = ord(char)
    return (
        0x3040 <= code <= 0x309F
        or 0x30A0 <= code <= 0x30FF
        or 0x4E00 <= code <= 0x9FFF
        or 0xFF66 <= code <= 0xFF9D
    )


def _is_garbled_signal_char(char: str) -> bool:
    code = ord(char)
    return (
        0x0800 <= code <= 0x083F
        or 0x0E00 <= code <= 0x0E7F
        or 0x1100 <= code <= 0x11FF
        or 0x1200 <= code <= 0x137F
        or 0x13A0 <= code <= 0x13FF
        or 0x1780 <= code <= 0x17FF
        or 0x1A00 <= code <= 0x1AFF
        or 0x2400 <= code <= 0x243F
        or 0x3400 <= code <= 0x4DBF
        or char in {"≉", "⚾", "࠙", "ࠚ"}
    )


def analyze_text_layer(text: str) -> dict[str, Any]:
    normalized = text.strip()
    char_count = len(normalized)
    japanese_char_count = sum(1 for char in normalized if _is_common_japanese_char(char))
    garbled_signal_count = sum(1 for char in normalized if _is_garbled_signal_char(char))
    japanese_term_count = sum(1 for term in JAPANESE_TERMS if term in normalized)
    japanese_signal_count = japanese_char_count + japanese_term_count

    if char_count == 0:
        return {
            "status": "empty_text_layer",
            "requires_manual_text_check": True,
            "reason": "No usable text was extracted from the PDF text layer.",
            "char_count": 0,
            "japanese_signal_count": 0,
            "garbled_signal_count": 0,
            "sample": "",
        }

    garbled_ratio = garbled_signal_count / max(char_count, 1)
    japanese_ratio = japanese_char_count / max(char_count, 1)
    if garbled_signal_count >= 5 and (garbled_ratio >= 0.12 or japanese_ratio < 0.25):
        status = "garbled_text_layer"
        needs_check = True
        reason = "The extracted text contains many cross-script or rare glyph signals, so table/date extraction should be manually checked or routed through vision."
    else:
        status = "readable"
        needs_check = False
        reason = "The PDF text layer contains usable Japanese admissions text."

    return {
        "status": status,
        "requires_manual_text_check": needs_check,
        "reason": reason,
        "char_count": char_count,
        "japanese_signal_count": japanese_signal_count,
        "japanese_char_count": japanese_char_count,
        "japanese_term_count": japanese_term_count,
        "garbled_signal_count": garbled_signal_count,
        "garbled_ratio": round(garbled_ratio, 4),
        "sample": normalized[:240],
    }


def _read_pdf_text(path: Path) -> str:
    pages = extract_text_per_page(path)
    return "\n".join(text for _page, text in sorted(pages.items()))


def _candidate_source_path(root: Path | None, candidates: list[str]) -> Path | None:
    if not candidates:
        return None
    first = Path(candidates[0])
    if root is None or first.is_absolute():
        return first
    return root / first


def audit_seed_source_text_layers(
    *,
    root: Path | None = ROOT,
    seeds: dict[str, dict[str, Any]] | None = None,
    text_by_path: dict[str, str] | None = None,
) -> dict[str, Any]:
    seed_map = seeds if seeds is not None else registered_seed_extractors()
    injected_text = text_by_path or {}
    items: list[dict[str, Any]] = []

    for seed_key, seed in sorted(seed_map.items()):
        candidates = [str(candidate) for candidate in seed.get("source_candidates") or []]
        source_path = _candidate_source_path(root, candidates)
        source_label = candidates[0] if candidates else ""

        if source_label in injected_text:
            text_health = analyze_text_layer(injected_text[source_label])
        elif source_path is None or not source_path.exists():
            text_health = {
                "status": "missing_source",
                "requires_manual_text_check": True,
                "reason": "The registered local source PDF is missing.",
                "char_count": 0,
                "japanese_signal_count": 0,
                "garbled_signal_count": 0,
                "sample": "",
            }
        else:
            text_health = analyze_text_layer(_read_pdf_text(source_path))

        items.append(
            {
                "id": seed_key,
                "source_path": str(source_path or source_label),
                "text_health": text_health,
            }
        )

    manual_needed = sum(1 for item in items if item["text_health"].get("requires_manual_text_check"))
    return {
        "passed": True,
        "summary": {
            "total": len(items),
            "readable": sum(1 for item in items if item["text_health"].get("status") == "readable"),
            "manual_text_check_needed": manual_needed,
            "missing_source": sum(1 for item in items if item["text_health"].get("status") == "missing_source"),
        },
        "items": items,
    }


def _summary_lines(report: dict[str, Any]) -> list[str]:
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    lines = [
        "source text health: advisory",
        f"seed sources: {summary.get('total', 0)}",
        f"readable text layers: {summary.get('readable', 0)}",
        f"manual/vision check recommended: {summary.get('manual_text_check_needed', 0)}",
    ]
    for item in report.get("items") or []:
        health = item.get("text_health") if isinstance(item, dict) else {}
        if isinstance(health, dict) and health.get("requires_manual_text_check"):
            lines.append(f"- {item.get('id')}: {health.get('status')}")
    return lines


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Audit seed PDF text-layer readability without blocking baseline checks.")
    parser.add_argument("--summary", action="store_true", help="Print a concise human-readable summary.")
    parser.add_argument("--output", default="", help="Optional path to write the JSON report.")
    args = parser.parse_args(argv)

    report = audit_seed_source_text_layers()
    if args.output:
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.summary:
        print("\n".join(_summary_lines(report)))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
