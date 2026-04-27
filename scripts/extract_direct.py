from __future__ import annotations

import argparse
import base64
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any
from urllib import request as urllib_request
from urllib.error import HTTPError

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.db import create_source_document, init_db, insert_staging_record, update_source_document  # noqa: E402
from scripts.json_parser import extract_json_payload  # noqa: E402
from scripts.pdf_render import render_pdf_to_images  # noqa: E402
from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402
from scripts.validator import validate  # noqa: E402

PROMPT_PATH = ROOT / "prompts" / "vision_prompt.md"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
DEFAULT_TEXT_MODEL = "gpt-5.4-mini"
DEFAULT_VISION_MODEL = "gpt-4o-mini"
MEIJI_REQUIRED_FACULTIES = [
    "法学部",
    "商学部",
    "政治経済学部",
    "文学部",
    "理工学部",
    "農学部",
    "経営学部",
    "情報コミュニケーション学部",
    "国際日本学部",
    "総合数理学部",
]


def _load_prompt() -> str:
    return PROMPT_PATH.read_text(encoding="utf-8")


def _load_api_key() -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        env_path = ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8-sig").splitlines():
                line = line.strip()
                if line.startswith("OPENAI_API_KEY="):
                    key = line.split("=", 1)[1].strip()
                    break
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return key


def _load_env_value(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    if value:
        return value
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8-sig").splitlines():
            line = line.strip()
            if line.startswith(name + "="):
                v = line.split("=", 1)[1].strip()
                if v:
                    return v
                break
    return default


TEXT_MODEL = _load_env_value("OPENAI_TEXT_MODEL", DEFAULT_TEXT_MODEL)
VISION_MODEL = _load_env_value("OPENAI_VISION_MODEL", DEFAULT_VISION_MODEL)


def _read_pdf_text(pdf_path: Path) -> tuple[str, dict[int, str]]:
    page_map = extract_text_per_page(pdf_path)
    texts = [f"=== PAGE {idx} ===\\n{text}" for idx, text in sorted(page_map.items()) if text]
    return "\\n\\n".join(texts), page_map


def _data_url_from_image(image_path: Path) -> str:
    mime = "image/png" if image_path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    return f"data:{mime};base64,{b64}"


def _call_openai(
    messages: list[dict[str, Any]],
    model: str,
    max_tokens: int = 12000,
    token_param: str = "max_tokens",
) -> dict[str, Any]:
    api_key = _load_api_key()
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0,
        token_param: max_tokens,
    }
    req = urllib_request.Request(
        OPENAI_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    last_error: Exception | None = None
    for attempt in range(3):
        try:
            with urllib_request.urlopen(req, timeout=240) as resp:
                raw = json.loads(resp.read().decode("utf-8"))
            break
        except HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < 2:
                time.sleep(2.0 + attempt * 2.0)
                last_error = RuntimeError(f"OpenAI API error {e.code}: {body}")
                continue
            raise RuntimeError(f"OpenAI API error {e.code}: {body}") from e
        except Exception as e:
            last_error = e
            if attempt < 2:
                time.sleep(1.5 + attempt)
                continue
            raise
    else:
        if last_error:
            raise last_error
        raise RuntimeError("OpenAI request failed")

    choice = raw["choices"][0]
    text = choice["message"]["content"]
    usage = raw.get("usage", {})
    finish_reason = choice.get("finish_reason")
    print("=== LLM RAW RESPONSE ===")
    print(text)
    print("=== END ===")
    print(
        "[tokens] input="
        + str(usage.get("prompt_tokens", 0))
        + ", output="
        + str(usage.get("completion_tokens", 0))
        + ", total="
        + str(usage.get("total_tokens", 0))
    )
    print("[finish_reason] " + str(finish_reason))
    result = extract_json_payload(text)
    result["_raw_response"] = text
    result["_usage"] = usage
    result["_finish_reason"] = finish_reason
    return result


def _build_system_prompt() -> str:
    return _load_prompt()


def _insert_result(
    doc_id: int,
    result: dict[str, Any],
    default_page: int | None = None,
    university: str = "",
    year: str = "",
) -> int:
    inserted = 0
    # Prefer caller-provided university/year over noisy model output.
    top_univ = university or str(result.get("university") or "").strip()
    top_year = year or str(result.get("admission_year") or "").strip()
    for rec in result.get("records") or []:
        if top_univ:
            rec["university"] = top_univ
        if top_year:
            rec["admission_year"] = top_year
        validated = validate(rec)
        page_number = validated.get("page_number")
        if page_number in ("", None):
            page_number = default_page
        insert_staging_record(doc_id, page_number, validated)
        inserted += 1
    return inserted


def _merge_record_group(group: list[dict[str, Any]]) -> dict[str, Any]:
    def score(rec: dict[str, Any]) -> tuple[float, int]:
        filled = sum(1 for v in rec.values() if str(v or "").strip())
        return (float(rec.get("confidence") or 0.0), filled)

    best = max(group, key=score)
    merged = dict(best)
    for rec in group:
        for key, value in rec.items():
            if not str(merged.get(key) or "").strip() and str(value or "").strip():
                merged[key] = value

    depts = []
    seen = set()
    for rec in group:
        dept = str(rec.get("department") or "").strip()
        if dept and dept not in seen:
            seen.add(dept)
            depts.append(dept)
    if depts:
        merged["department"] = " / ".join(depts)
    return merged


def _collapse_keio_faculties(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = {}
    order: list[str] = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        if faculty not in groups:
            groups[faculty] = []
            order.append(faculty)
        groups[faculty].append(rec)

    collapsed: list[dict[str, Any]] = []
    for faculty in order:
        group = groups[faculty]
        collapsed.append(group[0] if len(group) == 1 else _merge_record_group(group))
    return collapsed


def _normalize_keio_record(record: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(record)
    if not str(normalized.get("eju_math") or "").strip():
        normalized["eju_math"] = "?"
    return normalized


def _filter_non_private_student_records(result: dict[str, Any]) -> dict[str, Any]:
    records = []
    for rec in result.get("records") or []:
        text = " ".join(str(rec.get(k) or "") for k in ["admission_period", "faculty", "department", "warnings"])
        if any(flag in text for flag in ["第2種", "帰国生徒", "帰国子女"]):
            continue
        records.append(rec)
    new_result = dict(result)
    new_result["records"] = records
    return new_result


def _dedupe_by_faculty(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    best_by_faculty: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        if not faculty:
            continue
        if faculty not in best_by_faculty:
            best_by_faculty[faculty] = rec
            order.append(faculty)
            continue
        prev = best_by_faculty[faculty]
        prev_score = (float(prev.get("confidence") or 0.0), sum(1 for v in prev.values() if str(v or "").strip()))
        cur_score = (float(rec.get("confidence") or 0.0), sum(1 for v in rec.values() if str(v or "").strip()))
        if cur_score > prev_score:
            best_by_faculty[faculty] = rec
    return [best_by_faculty[f] for f in order]


def _supplement_meiji_missing_faculties(
    full_text: str,
    university: str,
    year: str,
    existing_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if university != "明治大学" or str(year) != "2026":
        return existing_records

    existing_faculties = {str(r.get("faculty") or "").strip() for r in existing_records}
    missing = [f for f in MEIJI_REQUIRED_FACULTIES if f not in existing_faculties]
    if not missing:
        return _dedupe_by_faculty(existing_records)

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {
            "role": "user",
            "content": (
                f"[Info] university={university} year={year} mode=text-supplement\n\n"
                "以下の学部だけを補完抽出してください。"
                "各学部につき1レコード、代表学科名のみ、重複禁止。"
                "不足学部一覧: "
                + "、".join(missing)
                + "。\n\n[全文テキスト]\n"
                + full_text
            ),
        },
    ]
    supplement = _call_openai(messages, TEXT_MODEL, max_tokens=2500, token_param="max_completion_tokens")
    extra = supplement.get("records") or []
    merged = existing_records + [r for r in extra if str(r.get("faculty") or "").strip() in missing]
    merged = _dedupe_by_faculty(merged)
    return merged


def _find_sparse_pages(page_map: dict[int, str], threshold: int = 200) -> list[int]:
    """Return page numbers whose text content is too short to contain a table."""
    return [page_num for page_num, text in page_map.items() if len(text.strip()) < threshold]


def _vision_patch_records(
    records: list[dict[str, Any]],
    sparse_pages: list[int],
    pdf_path: Path,
    university: str,
    year: str,
    doc_id: int,
) -> list[dict[str, Any]]:
    """For any records where key fields are empty, re-extract sparse pages via vision
    and backfill missing values. Generic — works for any university."""
    PATCH_FIELDS = ["english_requirement", "eju_japanese", "eju_math", "screening_method"]

    empty_ratio = sum(
        1 for r in records
        if not str(r.get("english_requirement") or "").strip()
    ) / max(len(records), 1)

    if empty_ratio < 0.3 or not sparse_pages:
        return records  # quality is fine, skip

    print(f"[direct] vision_patch triggered: {empty_ratio:.0%} records missing english_requirement, sparse_pages={sparse_pages}")

    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = render_pdf_to_images(pdf_path, out_dir)

    # Only render and send the sparse pages
    patch_records: list[dict[str, Any]] = []
    for page_num in sparse_pages:
        img_idx = page_num - 1
        if img_idx >= len(images):
            continue
        image_path = images[img_idx]
        try:
            messages = [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"[Info] university={university} year={year} mode=vision_patch page={page_num}\n"
                                "このページは表が画像化されています。"
                                "学部・学科ごとの英語外部試験要件・EJU要件を中心に抽出してください。"
                                "各レコードに faculty と english_requirement を必ず含めてください。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url_from_image(image_path)},
                        },
                    ],
                },
            ]
            result = _call_openai(messages, VISION_MODEL, max_tokens=6000, token_param="max_tokens")
            patch_records.extend(result.get("records") or [])
            print(f"[direct] vision_patch page={page_num}: got {len(result.get('records') or [])} records")
        except Exception as e:
            print(f"[direct] vision_patch_failed page={page_num}: {e}")

    if not patch_records:
        return records

    # Build lookup: faculty -> patch record
    patch_by_faculty: dict[str, dict[str, Any]] = {}
    for pr in patch_records:
        faculty = str(pr.get("faculty") or "").strip()
        if faculty:
            patch_by_faculty[faculty] = pr

    # Backfill empty fields in existing records
    patched = []
    for rec in records:
        faculty = str(rec.get("faculty") or "").strip()
        pr = patch_by_faculty.get(faculty)
        if pr:
            for field in PATCH_FIELDS:
                if not str(rec.get(field) or "").strip() and str(pr.get(field) or "").strip():
                    rec[field] = pr[field]
                    print(f"[direct] patched {faculty}.{field} = {pr[field]!r}")
        patched.append(rec)
    return patched


def _run_text_path(doc_id: int, pdf_path: Path, university: str, year: str) -> dict[str, Any]:
    full_text, page_map = _read_pdf_text(pdf_path)
    text_len = len(full_text.strip())
    print(f"[direct] text_length={text_len} pages={len(page_map)}")
    faculty_candidates: list[str] = []
    seen_faculty: set[str] = set()
    for m in re.finditer(r"[一-龥々ぁ-んァ-ンー・]+学部", full_text):
        name = m.group(0).strip()
        if name and name not in seen_faculty:
            seen_faculty.add(name)
            faculty_candidates.append(name)
    faculty_hint = ""
    if faculty_candidates:
        faculty_hint = "本文から検出した学部一覧: " + "、".join(faculty_candidates) + "。この一覧を漏れなくrecordsに含めてください。"

    messages = [
        {"role": "system", "content": _build_system_prompt()},
        {
            "role": "user",
            "content": (
                f"[Info] university={university} year={year} mode=text\n\n"
                "これは募集要項PDF全文の文字層です。単ページとして扱わず、全文から募集単位をまとめて抽出してください。"
                "各学部は学部名と代表学科名のみ記載してください。専攻レベルまで細分化しないこと。"
                "同一学部の重複レコードは禁止。各学部につき1レコードのみ出力してください。"
                "PDFに記載された全学部を漏れなく含めてください。records件数は学部数以上にしてください。"
                + faculty_hint +
                "records にはPDF全体の学部・学科ごとの記録を入れてください。"
                "本システムは外国人留学生（私費留学生）の募集要項のみを対象とします。"
                "帰国生徒・帰国子女・第2種に関する情報は抽出しないでください。\n\n"
                "[全文テキスト]\n"
                + full_text
            ),
        },
    ]
    result = _call_openai(messages, TEXT_MODEL, max_tokens=6000, token_param="max_completion_tokens")
    if university == "明治大学" and str(year) == "2026" and result.get("records"):
        result["records"] = _supplement_meiji_missing_faculties(full_text, university, year, result.get("records") or [])
    if university == "慶應義塾大学" and str(year) == "2026" and result.get("records"):
        result["records"] = [_normalize_keio_record(r) for r in _collapse_keio_faculties(result["records"])]
    if university == "東京大学" and str(year) == "2026" and result.get("records"):
        result = _filter_non_private_student_records(result)
    if not result.get("records"):
        raise RuntimeError("text_path returned 0 records")

    # Generic vision patch for image-based tables
    sparse_pages = _find_sparse_pages(page_map)
    if sparse_pages:
        result["records"] = _vision_patch_records(
            result.get("records") or [],
            sparse_pages,
            pdf_path,
            university,
            year,
            doc_id,
        )

    inserted = _insert_result(doc_id, result, university=university, year=year)
    return {
        "mode": "text",
        "pages": len(page_map),
        "text_length": text_len,
        "records": len(result.get("records") or []),
        "inserted": inserted,
        "failed_pages": [],
        "raw": result,
    }


def _run_vision_path(doc_id: int, pdf_path: Path, university: str, year: str) -> dict[str, Any]:
    out_dir = ROOT / "output_pages" / f"direct_{doc_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    images = render_pdf_to_images(pdf_path, out_dir)
    inserted = 0
    failed_pages: list[dict[str, Any]] = []
    last_raw: dict[str, Any] | None = None

    for page_num, image_path in enumerate(images, start=1):
        try:
            messages = [
                {"role": "system", "content": _build_system_prompt()},
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"[Info] university={university} year={year} mode=vision page={page_num}\n"
                                "これは単ページPDF画像です。ページ中の募集単位をまとめて JSON で返してください。"
                                "本システムは外国人留学生（私費留学生）の募集要項のみを対象とします。"
                                "帰国生徒・帰国子女・第2種に関する情報は抽出しないでください。"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": _data_url_from_image(image_path)},
                        },
                    ],
                },
            ]
            result = _call_openai(messages, VISION_MODEL, max_tokens=12000, token_param="max_tokens")
            if university == "慶應義塾大学" and str(year) == "2026" and result.get("records"):
                result["records"] = [_normalize_keio_record(r) for r in _collapse_keio_faculties(result["records"])]
            if university == "東京大学" and str(year) == "2026" and result.get("records"):
                result = _filter_non_private_student_records(result)
            records = result.get("records") or []
            for rec in records:
                if university:
                    rec["university"] = university
                if year:
                    rec["admission_year"] = year
                validated = validate(rec)
                if validated.get("page_number") in ("", None):
                    validated["page_number"] = page_num
                insert_staging_record(doc_id, page_num, validated)
                inserted += 1
            last_raw = result
        except Exception as e:
            failed_pages.append({"page": page_num, "error": str(e)})
            print(f"[direct] vision_failed page={page_num}: {e}")

    return {
        "mode": "vision",
        "pages": len(images),
        "records": inserted,
        "inserted": inserted,
        "failed_pages": failed_pages,
        "raw": last_raw,
    }


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Direct PDF-to-LLM extractor")
    p.add_argument("--pdf", required=True)
    p.add_argument("--university", required=True)
    p.add_argument("--year", required=True)
    p.add_argument("--url", default="")
    return p


def run_extraction(pdf_path: Path, university: str, year: str, url: str = "") -> dict[str, Any]:
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    init_db()
    doc_id = create_source_document(
        university=university,
        file_name=pdf_path.name,
        file_path=str(pdf_path),
        pdf_url=url,
        admission_year=year,
    )
    print(f"[direct] source_document id={doc_id}")

    full_text, _ = _read_pdf_text(pdf_path)
    if len(full_text.strip()) > 500:
        try:
            report = _run_text_path(doc_id, pdf_path, university, year)
            status = "text_completed"
        except Exception as e:
            print(f"[direct] text_path_failed: {e}")
            report = _run_vision_path(doc_id, pdf_path, university, year)
            status = "vision_completed"
    else:
        report = _run_vision_path(doc_id, pdf_path, university, year)
        status = "vision_completed"

    update_source_document(doc_id, status=status)
    return {
        "doc_id": doc_id,
        "status": status,
        "mode": report["mode"],
        "pages": report.get("pages"),
        "records": report.get("records"),
        "inserted": report.get("inserted"),
        "failed_pages": report.get("failed_pages", []),
    }


def main() -> int:
    args = build_parser().parse_args()
    pdf_path = Path(args.pdf)
    if not pdf_path.exists():
        print(f"[direct] PDF not found: {pdf_path}")
        return 2
    result = run_extraction(pdf_path, args.university, str(args.year), args.url or "")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
