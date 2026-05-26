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

SOURCE_URL = "https://secondhome.chukyogakuin-u.ac.jp/media/youkou-foreign-2027.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "chukyo_gakuin_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "中京学院大学",
        "admission_year": "2027",
        "application_period": "2027留学生入学試験は6/1から募集開始。締切は第1回7/8、第2回8/12、第3回9/9、第4回10/7、第5回11/11、第6回12/9まで、いずれも必着。",
        "deadline_rule": "各回の締切日必着。年明け以降は募集状況を見ながら判断し、募集しない場合もあるため、出願前に必ず問い合わせや事前の相談をすること。",
        "eligibility": "外国籍を有し、外国において日本の高等学校に相当する学校を卒業、または12年以上の学校教育を修了し、その国で大学入学資格を有する者。入学に支障のない在留資格を有することが可能な者。",
        "required_documents": "入学志願票、留学生学歴等記載、志望理由書、経費支弁書、推薦書(該当者のみ)、入学金免除申請書(該当者のみ)、写真2枚、高等学校の卒業証明書、高等学校の成績証明書、日本国内で在籍している学校の証明書、出願資格を満たす証明、日本語能力がわかる公的証明書(JLPT等)、パスポートコピー、在留カードコピー。",
        "screening_method": "一般選抜は書類審査、面接、日本語テスト。指定校推薦選抜は日本語テストを免除。試験当日の評価と提出書類を審査して総合判定。",
        "screening_schedule": "試験日は第1回7月16日、第2回8月20日、第3回9月17日、第4回10月15日、第5回11月19日、第6回12月17日。選抜試験時間は13:00から15:00予定。",
        "result_date": "合格発表は第1回7月24日、第2回8月28日、第3回9月25日、第4回10月23日、第5回11月27日、第6回12月24日に発送。",
        "enrollment_period": "手続き締切日は第1回から第3回が10月23日、第4回が11月27日、第5回が12月24日、第6回が1月15日。期日までに入学手続金を納入し、入学手続書類を提出すると入学許可書を発行。",
        "confidence": 0.96,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Chukyo Gakuin 2027 foreign student selection student application guideline."],
    }


def extract_chukyo_gakuin_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["中京学院大学", "2027", "外国人留学生選抜"]):
        return []
    if "出願書類" not in compact and "提出書類" not in compact:
        return []
    if not _has_all(compact, ["経営学部", "看護学部", "日本語テスト"]):
        return []

    common = _common()
    return [
        {
            **common,
            "id": "chukyo-gakuin-2027-business",
            "faculty": "経営学部",
            "department": "経営学科",
            "eligibility": common["eligibility"] + " 経営学部は日本語能力としてB2相当、指定校推薦選抜では例としてJLPT N2以上。",
            "jlpt_requirement": "経営学部は日本語教育の参照枠でB2相当。指定校推薦選抜では公的試験の結果がB2相当、例としてJLPTはN2以上。",
            "evidence": "Official 2027 student application guideline p.1, p.4, p.5, p.6-p.7, and p.10: eligibility, B2/JLPT standard, selection schedule, required documents, and enrollment procedure.",
        },
        {
            **common,
            "id": "chukyo-gakuin-2027-nursing",
            "faculty": "看護学部",
            "department": "看護学科",
            "application_period": "2027留学生入学試験は6/1から募集開始。第6回までは12/9締切、年明け以降は募集状況により判断。",
            "eligibility": common["eligibility"] + " 看護学部は日本語教育の参照枠でB2以上を日本語能力基準とする。",
            "jlpt_requirement": "看護学部は日本語教育の参照枠でB2以上。出願書類として日本語能力がわかる公的証明書(JLPT等)を提出。",
            "result_date": "合格発表は各回の期日に発送。",
            "evidence": "Official 2027 student application guideline p.1, p.4, p.5, p.7, and p.10: nursing eligibility, B2-or-higher standard, documents, schedule, and enrollment procedure.",
        },
    ]


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return Path(args.text).read_text(encoding="utf-8")
    if args.pdf:
        pages = extract_text_per_page(args.pdf)
        return "\n".join(text for _page, text in sorted(pages.items()))
    raise ValueError("--text or --pdf is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Chukyo Gakuin 2027 foreign student selection guideline.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_chukyo_gakuin_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(json.dumps({"records": records, "record_count": len(records), "source": "chukyo_gakuin_2027_undergrad_seed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
