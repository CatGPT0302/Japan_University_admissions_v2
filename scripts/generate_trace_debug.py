from __future__ import annotations

import json
import re
import sqlite3
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.pdf_text_extractor import extract_text_per_page

DB_PATH = ROOT / "database" / "admissions_v2.db"
OUTPUT_PATH = ROOT / "trace_debug.json"
MAX_ROWS = 5
SNIPPET_MAX_LEN = 90


def _normalize_text(text: str) -> str:
    # NFKC helps align full-width/half-width symbols used in Japanese PDFs.
    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _extract_dates(text: str) -> list[str]:
    value = _normalize_text(text)
    if not value:
        return []
    dates = re.findall(r"\d{4}年\d{1,2}月\d{1,2}日", value)
    return list(dict.fromkeys(dates))


def _clip_snippet(text: str, max_len: int = SNIPPET_MAX_LEN) -> str:
    text = _normalize_text(text)
    if len(text) <= max_len:
        return text
    return text[: max_len - 1].rstrip() + "…"


def _snippet_from_exact(normalized_page: str, normalized_value: str) -> str:
    pos = normalized_page.find(normalized_value)
    if pos == -1:
        return ""
    return _clip_snippet(normalized_page[pos : pos + len(normalized_value)])


def _snippet_from_date_range(normalized_page: str, dates: list[str]) -> str:
    if not dates:
        return ""
    positions: list[tuple[int, str]] = []
    for d in dates:
        p = normalized_page.find(d)
        if p >= 0:
            positions.append((p, d))
    if not positions:
        return ""
    positions.sort(key=lambda x: x[0])
    start_pos, start_date = positions[0]
    end_pos, end_date = positions[-1]
    start = start_pos
    end = min(len(normalized_page), end_pos + len(end_date) + 24)
    # If only one date found, keep a small local window.
    if len(positions) == 1:
        end = min(len(normalized_page), start_pos + len(start_date) + 24)
    return _clip_snippet(normalized_page[start:end])


def _count_matched_dates(normalized_page: str, dates: list[str]) -> int:
    return sum(1 for d in dates if d and d in normalized_page)


def _pick_page_and_snippet(
    application_period: str,
    hinted_page: int | None,
    page_text_map: dict[int, str],
) -> tuple[int, str, str]:
    normalized_value = _normalize_text(application_period)
    dates = _extract_dates(application_period)

    def page_text(page_num: int) -> str:
        return _normalize_text(page_text_map.get(page_num, ""))

    # 1) Try hinted page first.
    if hinted_page and hinted_page in page_text_map:
        hinted_text = page_text(hinted_page)
        if normalized_value and normalized_value in hinted_text:
            return (
                int(hinted_page),
                _snippet_from_exact(hinted_text, normalized_value),
                "exact: full application_period string matched on hinted page",
            )
        matched = _count_matched_dates(hinted_text, dates)
        if matched >= 1:
            return (
                int(hinted_page),
                _snippet_from_date_range(hinted_text, dates),
                "partial: date tokens matched on hinted page; separators/time text differ",
            )

    # 2) Global exact match.
    if normalized_value:
        for p in sorted(page_text_map):
            text = page_text(p)
            if normalized_value in text:
                return (
                    int(p),
                    _snippet_from_exact(text, normalized_value),
                    "exact: full application_period string matched in page text",
                )

    # 3) Global partial match by best date-token overlap.
    best_page = 0
    best_score = -1
    for p in sorted(page_text_map):
        score = _count_matched_dates(page_text(p), dates)
        if score > best_score:
            best_score = score
            best_page = p
    if best_page > 0 and best_score >= 1:
        text = page_text(best_page)
        return (
            int(best_page),
            _snippet_from_date_range(text, dates),
            "partial: date tokens matched; page selected by highest overlap",
        )

    # 4) Uncertain fallback.
    fallback_page = int(min(page_text_map.keys())) if page_text_map else 1
    fallback_text = page_text(fallback_page)
    snippet = _clip_snippet(fallback_text[:60])
    return (
        fallback_page,
        snippet,
        "uncertain: no strong date/string match; fallback page used",
    )


def load_candidate_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    sql = """
    SELECT
      ar.id AS record_id,
      ar.university,
      ar.faculty,
      ar.department,
      ar.application_period,
      ar.document_id,
      ar.source_staging_id,
      s.page_number AS staging_page_number,
      sd.file_path
    FROM admission_records ar
    LEFT JOIN admission_records_staging s
      ON s.id = ar.source_staging_id
    LEFT JOIN source_documents sd
      ON sd.id = ar.document_id
    WHERE ar.application_period IS NOT NULL
      AND TRIM(ar.application_period) <> ''
    ORDER BY ar.id ASC
    LIMIT ?
    """
    return conn.execute(sql, (MAX_ROWS,)).fetchall()


def main() -> int:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = load_candidate_rows(conn)
    conn.close()

    trace_entries: list[dict[str, Any]] = []
    pdf_cache: dict[str, dict[int, str]] = {}

    for row in rows:
        pdf_path = str(row["file_path"] or "").strip()
        if not pdf_path:
            continue
        if pdf_path not in pdf_cache:
            pdf_cache[pdf_path] = extract_text_per_page(pdf_path)
        page_text_map = pdf_cache[pdf_path]
        source_page, source_snippet, risk_reason = _pick_page_and_snippet(
            application_period=str(row["application_period"] or ""),
            hinted_page=row["staging_page_number"],
            page_text_map=page_text_map,
        )
        trace_entries.append(
            {
                "university": row["university"],
                "faculty": row["faculty"],
                "department": row["department"],
                "field_name": "application_period",
                "extracted_value": row["application_period"],
                "source_page": int(source_page),
                "source_snippet": source_snippet,
                "risk_reason": risk_reason,
            }
        )

    OUTPUT_PATH.write_text(json.dumps(trace_entries, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"generated {len(trace_entries)} entries -> {OUTPUT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
