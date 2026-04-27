from __future__ import annotations

import json
import re
from typing import Any


def _strip_fence(text: str) -> str:
    s = text.strip()
    if not s.startswith("```"):
        return s
    for part in s.split("```"):
        part = part.strip()
        if not part:
            continue
        if part.startswith("json"):
            part = part[4:].strip()
        if part.startswith("{") or part.startswith("["):
            return part
    return s


def _extract_partial_records(text: str) -> dict[str, Any] | None:
    records_match = re.search(r'"records"\s*:\s*\[', text)
    if not records_match:
        return None

    university_match = re.search(r'"university"\s*:\s*"([^"]*)"', text)
    year_match = re.search(r'"admission_year"\s*:\s*"([^"]*)"', text)

    records: list[dict[str, Any]] = []
    start = records_match.end()
    depth = 0
    in_string = False
    escape = False
    buf: list[str] = []

    for ch in text[start:]:
        if depth == 0:
            if ch == "{":
                depth = 1
                buf = ["{"]
            elif ch == "]":
                break
            continue

        buf.append(ch)

        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_string = False
            continue

        if ch == '"':
            in_string = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                snippet = "".join(buf)
                try:
                    rec = json.loads(snippet)
                except Exception:
                    rec = None
                if isinstance(rec, dict):
                    records.append(rec)
                buf = []

    if not records:
        return None

    return {
        "university": university_match.group(1) if university_match else "",
        "admission_year": year_match.group(1) if year_match else "",
        "records": records,
    }


def extract_json_payload(text: str) -> dict[str, Any]:
    s = _strip_fence(text)

    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    decoder = json.JSONDecoder()
    starts = [i for i, ch in enumerate(s) if ch == "{"]

    for start in starts:
        try:
            obj, _ = decoder.raw_decode(s[start:])
        except Exception:
            continue
        if isinstance(obj, dict) and "records" in obj:
            return obj

    partial = _extract_partial_records(s)
    if partial is not None:
        return partial

    for start in starts:
        try:
            obj, _ = decoder.raw_decode(s[start:])
        except Exception:
            continue
        if isinstance(obj, dict):
            return obj

    raise ValueError("No valid JSON found in LLM response")
