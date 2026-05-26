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

SOURCE_URL = "https://www.keio.ac.jp/files/66f9e69c6550ffb5f9da5ee62c5be61aaba0f159b4e619e4752ebdee5b207fba"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def extract_keio_2027_medicine_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["慶應義塾大学", "2027年度", "医学部外国人留学生対象", "入学試験募集要項"]):
        return []
    if not _has_all(compact, ["医学部", "第1次選考", "第2次選考", "総合問題", "模擬講義", "面接"]):
        return []

    return [
        {
            "source_pdf": "keio_2027_medicine.pdf",
            "source_document": SOURCE_URL,
            "university": "慶應義塾大学",
            "admission_year": "2027",
            "faculty": "医学部",
            "department": "医学科",
            "application_period": "Webエントリー: 2026年7月3日(金)10:00～7月14日(火)16:00 / 出願書類の郵送: 2026年7月3日(金)～7月15日(水)",
            "deadline_rule": "速達・簡易書留 / 締切日必着",
            "eligibility": "学校教育課程12年以上を修めた者、または2027年3月31日までに修める見込みの者 / 海外の学校教育制度に基づく中学校および高等学校の全期間の課程を修了した者",
            "required_documents": "出願書類チェックリスト / 入学志願票 / 入学志願者調書 / 志望理由書 / エッセイ / 成績証明書 / 推薦状 / 日本留学試験結果 / TOEFL iBTもしくはIELTS Academic Moduleの結果 / パスポートのコピー",
            "eju_session": "2024年度第2回 / 2025年度第1回 / 2025年度第2回 / 2026年度第1回",
            "eju_subjects": "日本留学試験結果を提出。基準点は設けていません。",
            "english_requirement": "TOEFL iBTもしくはIELTS Academic Module。受験期間: 2024年9月1日～2026年6月30日。基準点は設けていません。",
            "screening_method": "第1次選考: 書類選考 / 第2次選考: 総合問題・模擬講義・面接",
            "screening_schedule": "第2次選考: 2026年9月27日(日) 8:45集合 / 9:00～ / 信濃町キャンパス",
            "result_date": "第1次選考合格発表: 2026年9月8日(火)10:00 / 最終合格発表: 2026年9月29日(火)10:00",
            "enrollment_period": "2026年11月30日(月)～12月11日(金)",
            "evidence": "表紙・出願期間: p.1 / 募集人員・日程、選考方法: p.3 / 出願資格: p.4-p.6 / 出願書類・EJU・TOEFL・IELTS: p.12-p.19 / 第2次選考: p.21 / 合格発表・入学手続: p.24-p.25",
            "confidence": 0.99,
            "needs_review": True,
            "warnings": ["Deterministic seed extraction from the official Keio 2027 Faculty of Medicine international student admissions guide; extend by human review."],
        }
    ]


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return Path(args.text).read_text(encoding="utf-8")
    if args.pdf:
        pages = extract_text_per_page(args.pdf)
        return "\n".join(text for _page, text in sorted(pages.items()))
    raise ValueError("--text or --pdf is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Keio 2027 medicine international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_keio_2027_medicine_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "keio_2027_medicine_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
