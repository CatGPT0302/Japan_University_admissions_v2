from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable


@dataclass(frozen=True)
class VisionDraftResult:
    records: list[dict[str, Any]]
    global_fields: dict[str, Any]
    finish_reason: str


def page_numbers_from_images(images: list[Path]) -> list[int]:
    numbers: list[int] = []
    for index, image in enumerate(images, 1):
        stem = image.stem
        digits = "".join(char for char in stem if char.isdigit())
        numbers.append(int(digits) if digits else index)
    return numbers


def extract_with_batches(
    images: list[Path],
    *,
    university: str,
    year: str,
    batch_size: int,
    call_llm: Callable[[list[Path], str, str, list[int]], tuple[str, str]],
    parse_model_response: Callable[[str], dict[str, Any]],
    merge_global_fields: Callable[[dict[str, Any], dict[str, Any]], dict[str, Any]],
    apply_global_fields: Callable[[list[dict[str, Any]], dict[str, Any]], list[dict[str, Any]]],
    dedupe_records: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
) -> VisionDraftResult:
    batch_size = max(1, batch_size)
    page_numbers = page_numbers_from_images(images)
    all_records: list[dict[str, Any]] = []
    global_fields: dict[str, Any] = {}
    finish_reasons: list[str] = []

    for start in range(0, len(images), batch_size):
        batch = images[start : start + batch_size]
        batch_page_numbers = page_numbers[start : start + len(batch)]
        print(
            f"[full-vision] batch pages {batch_page_numbers[0]}-{batch_page_numbers[-1]} ({start + len(batch)} / {len(images)})",
            flush=True,
        )
        raw_text, finish_reason = call_llm(batch, university, year, batch_page_numbers)
        finish_reasons.append(finish_reason)
        parsed = parse_model_response(raw_text)
        chunk_global = parsed.get("global_fields") if isinstance(parsed.get("global_fields"), dict) else {}
        global_fields = merge_global_fields(global_fields, chunk_global)
        all_records.extend([dict(item) for item in parsed.get("records") or [] if isinstance(item, dict)])

    records = dedupe_records(apply_global_fields(all_records, global_fields))
    finish_reason = "/".join(sorted(set(filter(None, finish_reasons))))
    return VisionDraftResult(records=records, global_fields=global_fields, finish_reason=finish_reason)
