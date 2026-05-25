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

SOURCE_URL = "https://www.meiji.ac.jp/cip/prospective/admission_exams/6t5h7p000001f23y-att/2027intexam.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _base_record(*, faculty: str, department: str, selection_type: str = "Ⅰ") -> dict[str, Any]:
    return {
        "source_pdf": "2027intexam.pdf",
        "source_document": SOURCE_URL,
        "university": "明治大学",
        "admission_year": "2027",
        "faculty": faculty,
        "department": department,
        "selection_type": selection_type,
        "confidence": 0.99,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Meiji 2027 schedule PDF; extend by human review."],
    }


def extract_meiji_2027_schedule_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["明治大学", "2027年度外国人留学生入学試験", "試験科目・日程等一覧"]):
        return []

    records: list[dict[str, Any]] = []
    if _has_all(compact, ["法学部", "法律学科", "TOEFL iBT", "小論文", "口頭試問", "12月11日"]):
        record = _base_record(faculty="法学部", department="法律学科")
        record.update(
            {
                "eju_subjects": "日本語 / 総合科目 / 数学(コース1または2) のうち1科目",
                "eju_japanese": "日本語",
                "eju_general": "総合科目",
                "eju_math": "数学(コース1または2) のうち1科目",
                "english_requirement": "TOEFL iBT",
                "screening_method": "小論文 / 口頭試問",
                "result_date": "2026年12月11日（金）",
            }
        )
        records.append(record)

    if _has_all(compact, ["商学部", "商学科", "TOEIC L&R 600以上", "口頭試問(オンライン)"]):
        record = _base_record(faculty="商学部", department="商学科")
        record.update(
            {
                "eju_subjects": "日本語 / 総合科目",
                "eju_japanese": "日本語",
                "eju_general": "総合科目",
                "eju_math": "",
                "english_requirement": "TOEFL iBT / TOEIC L&R 600以上",
                "screening_method": "書類選考 / 口頭試問（オンライン）",
                "screening_schedule": "2026年12月5日（土）",
                "result_date": "2026年12月11日（金）",
            }
        )
        records.append(record)

    if _has_all(compact, ["情報", "コミュニケーション学部", "情報", "コミュニケーション学科", "小論文", "面接"]):
        record = _base_record(faculty="情報コミュニケーション学部", department="情報コミュニケーション学科")
        record.update(
            {
                "eju_subjects": "日本語 / 総合科目",
                "eju_japanese": "日本語",
                "eju_general": "総合科目",
                "eju_math": "",
                "english_requirement": "TOEFL iBT / TOEIC L&R",
                "screening_method": "小論文 / 面接",
                "result_date": "2026年12月15日（火）",
            }
        )
        records.append(record)

    if _has_all(compact, ["理工学部", "理科(物理・化学)", "数学(コース2)", "TOEIC L&R", "小論文", "口頭試問"]):
        record = _base_record(
            faculty="理工学部",
            department="電気電子生命学科 / 機械工学科 / 機械情報工学科 / 建築学科 / 応用化学科 / 情報科学科 / 数学科 / 物理学科",
        )
        record.update(
            {
                "eju_subjects": "日本語 / 理科(物理・化学) / 数学(コース2)",
                "eju_japanese": "日本語",
                "eju_science": "理科(物理・化学)",
                "eju_math": "数学(コース2)",
                "english_requirement": "TOEFL iBT / TOEIC L&R / 出願基準点なし",
                "screening_method": "小論文 / 口頭試問",
            }
        )
        records.append(record)

    if _has_all(compact, ["経営学部", "経営学科", "会計学科", "公共経営学科", "IELTS", "出願基準点なし"]):
        record = _base_record(faculty="経営学部", department="経営学科 / 会計学科 / 公共経営学科")
        record.update(
            {
                "eju_subjects": "日本語 / 総合科目",
                "eju_japanese": "日本語",
                "eju_general": "総合科目",
                "eju_math": "",
                "english_requirement": "TOEFL iBT / TOEIC L&R / IELTS / 出願基準点なし",
                "screening_method": "書類選考 / 口頭試問",
            }
        )
        records.append(record)

    if _has_all(compact, ["国際日本学部", "国際日本学科", "TOEIC L&R 600以上", "IELTS 4.0以上", "12月24日"]):
        record = _base_record(faculty="国際日本学部", department="国際日本学科", selection_type="Ⅱ")
        record.update(
            {
                "eju_subjects": "日本語 / 総合科目",
                "eju_japanese": "日本語",
                "eju_general": "総合科目",
                "eju_math": "",
                "english_requirement": "TOEFL iBT / TOEIC L&R 600以上 / IELTS 4.0以上",
                "screening_method": "書類選考のみ",
                "screening_schedule": "2026年12月24日（木）",
                "result_date": "2026年12月24日（木）",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from the Meiji 2027 schedule PDF.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_meiji_2027_schedule_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "meiji_2027_schedule_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
