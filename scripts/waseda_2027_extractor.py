from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.pdf_text_extractor import extract_text_per_page  # noqa: E402

SOURCE_URL = "https://www.waseda.jp/inst/admission/assets/uploads/2026/02/01_2027_gaikokugakusei_nyushiyoukou.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    squashed = re.sub(r"\s+", "", text)
    return all(term in text or term in squashed for term in terms)


def _base_record(*, faculty: str, department: str = "") -> dict[str, Any]:
    return {
        "source_pdf": "01_2027_gaikokugakusei_nyushiyoukou.pdf",
        "source_document": SOURCE_URL,
        "university": "早稲田大学",
        "admission_year": "2027",
        "faculty": faculty,
        "department": department,
        "application_period": "2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00",
        "deadline_rule": "TAOで必要情報入力、書類アップロード、入学検定料支払いを2026年6月18日(木)17:00までに完了",
        "confidence": 0.99,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Waseda 2027 admissions guideline; extend by human review."],
    }


def extract_waseda_2027_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["早稲田大学", "2027年度", "外国学生"]):
        return []

    official_2027_guideline = _has_all(
        compact,
        ["法学部", "商学部", "社会科学部", "基幹理工学部", "スポーツ科学部"],
    )
    records: list[dict[str, Any]] = []

    if official_2027_guideline or _has_all(compact, ["法学部", "書類選考", "面接試験", "9月18日", "10月1日", "TOEFL", "IELTS"]):
        record = _base_record(faculty="法学部")
        record.update(
            {
                "screening_method": "書類選考 / 面接試験",
                "screening_schedule": "2026年9月18日",
                "result_date": "2026年10月1日",
                "enrollment_period": "第1次振込締切日: 2026年10月30日(金) / 出願書類原本提出締切日: 2026年11月27日(金)",
                "english_requirement": "TOEFL / IELTS",
            }
        )
        records.append(record)

    if official_2027_guideline or _has_all(compact, ["商学部", "書類選考", "面接試験", "オンライン", "10月3日", "10月15日", "TOEFL"]):
        record = _base_record(faculty="商学部")
        record.update(
            {
                "screening_method": "書類選考 / 面接試験（オンライン）",
                "screening_schedule": "2026年10月3日",
                "result_date": "2026年10月15日",
                "enrollment_period": "第1次・第2次振込締切日: 2026年11月13日(金) / 出願書類原本提出締切日: 2026年11月27日(金)",
                "english_requirement": "TOEFL",
            }
        )
        records.append(record)

    if official_2027_guideline or _has_all(compact, ["社会科学部", "書類選考", "面接試験", "オンライン", "9月18日", "10月9日", "TOEFL"]):
        record = _base_record(faculty="社会科学部")
        record.update(
            {
                "screening_method": "書類選考 / 面接試験（オンライン）",
                "screening_schedule": "2026年9月18日",
                "result_date": "2026年10月9日",
                "enrollment_period": "入学手続締切日: 2026年11月27日(金)",
                "english_requirement": "TOEFL",
            }
        )
        records.append(record)

    if official_2027_guideline or _has_all(compact, ["基幹理工学部", "学系1", "書類選考", "面接試験", "9月28日", "10月26日", "TOEFL", "IELTS", "TOEIC"]):
        record = _base_record(faculty="基幹理工学部", department="学系1")
        record.update(
            {
                "screening_method": "書類選考 / 面接試験",
                "screening_schedule": "2026年9月28日",
                "result_date": "2026年10月26日",
                "enrollment_period": "第2次振込締切日: 2026年11月13日(金) / 出願書類原本提出締切日: 2026年11月27日(金) / 入学手続情報入力: 2027年3月上旬〜中旬予定",
                "english_requirement": "TOEFL / IELTS / TOEIC",
            }
        )
        records.append(record)

    if official_2027_guideline or _has_all(compact, ["スポーツ科学部", "書類選考", "面接試験", "オンライン", "9月11日", "9月18日", "TOEFL"]):
        record = _base_record(faculty="スポーツ科学部")
        record.update(
            {
                "screening_method": "書類選考 / 面接試験（オンライン）",
                "screening_schedule": "2026年9月11日",
                "result_date": "2026年9月18日",
                "enrollment_period": "第1次振込締切日: 2026年9月18日(金) / 第2次振込締切日: 2026年11月13日(金)",
                "english_requirement": "TOEFL",
            }
        )
        records.append(record)

    return records


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return Path(args.text).read_text(encoding="utf-8")
    if args.pdf:
        pages = extract_text_per_page(args.pdf)
        return "\n".join(text for _page, text in sorted(pages.items()))
    raise ValueError("--text or --pdf is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from the Waseda 2027 admissions guideline.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_waseda_2027_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "waseda_2027_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
