from __future__ import annotations
"""
Deprecated module.

Anthropic extraction is kept for historical reference only and is no longer
used by default entry points (CLI/API/Streamlit/pipeline wrapper).
"""
import base64
import json
import os
import re
from pathlib import Path
from urllib import request as urllib_request
from urllib.error import HTTPError

PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "vision_prompt.md"
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-sonnet-4-6"


def _load_prompt():
    return PROMPT_PATH.read_text(encoding="utf-8")


def _image_to_base64(image_path):
    return base64.b64encode(Path(image_path).read_bytes()).decode("utf-8")


def _fix_json_text(text):
    """Fix common LLM JSON formatting issues."""
    text = text.strip()
    if text.startswith("```"):
        for part in text.split("```"):
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            if part.startswith("{"):
                text = part
                break

    text = re.sub(r'[""„‟″‶＂「」『』﹁﹂]', '"', text)
    text = re.sub(r'[''‚‛]', "'", text)
    text = re.sub(r'(?<!\\)"{2,}', '"', text)
    text = re.sub(r'":\s*"(?=[,\n\r])', '": ""', text)

    open_braces = text.count('{') - text.count('}')
    open_brackets = text.count('[') - text.count(']')
    if open_braces > 0 or open_brackets > 0:
        stripped = text.rstrip().rstrip(',')
        last = stripped[-1] if stripped else ''
        if last not in ('"', '}', ']', '0', '1', '2', '3', '4', '5', '6', '7', '8', '9'):
            stripped += '"'
        text = stripped
        text += ']' * open_brackets
        text += '}' * open_braces

    return text


def _extract_partial_payload(text):
    university_match = re.search(r'"university"\s*:\s*"([^"]*)"', text)
    year_match = re.search(r'"admission_year"\s*:\s*"([^"]*)"', text)
    records_match = re.search(r'"records"\s*:\s*\[', text)
    if not records_match:
        return None

    start = records_match.end()
    records = []
    depth = 0
    in_string = False
    escape = False
    current: list[str] = []

    for ch in text[start:]:
        if depth == 0:
            if ch == "{":
                depth = 1
                current = ["{"]
            elif ch == "]":
                break
            continue

        current.append(ch)

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
                snippet = "".join(current)
                try:
                    rec = json.loads(snippet)
                except Exception:
                    try:
                        rec = json.loads(_fix_json_text(snippet))
                    except Exception:
                        rec = None
                if isinstance(rec, dict):
                    records.append(rec)
                current = []

    if depth > 0 and current:
        snippet = "".join(current).rstrip().rstrip(",")
        open_braces = snippet.count("{") - snippet.count("}")
        if open_braces > 0:
            repaired = snippet + ("}" * open_braces)
            try:
                rec = json.loads(_fix_json_text(repaired))
            except Exception:
                rec = None
            if isinstance(rec, dict):
                records.append(rec)

    if not records:
        return None

    return {
        "university": university_match.group(1) if university_match else "",
        "admission_year": year_match.group(1) if year_match else "",
        "records": records,
    }


def _extract_json(text):
    text = _fix_json_text(text)
    try:
        obj = json.loads(text)
        if isinstance(obj, dict):
            return obj
    except Exception:
        pass

    decoder = json.JSONDecoder()
    starts = [i for i, c in enumerate(text) if c == "{"]

    for start in starts:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict) and "records" in obj:
                return obj
        except Exception:
            continue

    for start in starts:
        snippet = text[start:]
        last_comma = max(snippet.rfind(",\n"), snippet.rfind(", "), snippet.rfind(","))
        if last_comma > 0:
            trimmed = snippet[:last_comma]
            ob = trimmed.count("{") - trimmed.count("}")
            obr = trimmed.count("[") - trimmed.count("]")
            candidate = trimmed + "]" * obr + "}" * ob
            try:
                obj, _ = decoder.raw_decode(candidate)
                if isinstance(obj, dict) and "records" in obj:
                    return obj
            except Exception:
                continue

    partial = _extract_partial_payload(text)
    if partial is not None:
        return partial

    for start in starts:
        try:
            obj, _ = decoder.raw_decode(text[start:])
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue

    raise ValueError("No valid JSON found: " + text[:400])


def _load_api_key() -> str:
    key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        env_path = Path(__file__).resolve().parent.parent / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line.startswith("ANTHROPIC_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    return key


def extract_page(image_path, metadata):
    api_key = _load_api_key()
    prompt = _load_prompt()
    b64 = _image_to_base64(image_path)
    suffix = Path(image_path).suffix.lower()
    media_type = "image/png" if suffix == ".png" else "image/jpeg"
    meta_hint = (
        "\n\n[Info] university=" + metadata.get("university", "")
        + " year=" + metadata.get("admission_year", "")
        + " page=" + metadata.get("page_number", "")
    )

    payload = {
        "model": MODEL,
        "max_tokens": 16000,
        "messages": [{
            "role": "user",
            "content": [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": media_type,
                        "data": b64,
                    },
                },
                {
                    "type": "text",
                    "text": prompt + meta_hint,
                },
            ],
        }],
    }

    req = urllib_request.Request(
        API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )

    try:
        with urllib_request.urlopen(req, timeout=120) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError("Anthropic API error " + str(e.code) + ": " + body) from e

    text = raw["content"][0]["text"]
    usage = raw.get("usage", {})
    print("  [tokens] input=" + str(usage.get("input_tokens", 0))
          + ", output=" + str(usage.get("output_tokens", 0)))

    result = _extract_json(text)
    result["_raw_response"] = text
    return result
