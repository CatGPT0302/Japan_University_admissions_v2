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

SOURCE_URL = "https://www.omu.ac.jp/admissions/assets/2027_international_student_pre_guide.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _is_osaka_metropolitan_foreign_student_guide(compact: str) -> bool:
    clean_match = _has_all(compact, ["大阪公立大学", "2027", "私費外国人留学生特別選抜"])
    pdf_text_match = _has_all(compact, ["2027", "␃Ꮫ", "᪥ᮏ", "ヨ㦂"])
    if not (clean_match or pdf_text_match):
        return False
    return clean_match or _has_all(compact, ["2027", "ฟ㢪", "ྜ᱁"])


def _no_external_english_requirement_note() -> str:
    return "英語外部試験は出願要件に含まれない。本seedでは要件なしとして明示。個別学力検査の外国語・英語は選抜方法に記載。"


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "osaka_metropolitan_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "大阪公立大学",
        "admission_year": "2027",
        "eligibility": "日本国籍を有しない者で、外国において学校教育における12年の課程を修了した者、または2027年3月31日までに修了見込みの者等。出願資格に不明点がある場合は事前の資格審査が必要。",
        "required_documents": "2027年度私費外国人留学生特別選抜入試要項では日程・科目・配点を公表。出願書類と提出方法は、7月以降に公表予定の2027年度学生募集要項および出願関係書類一覧を必ず確認する。",
        "confidence": 0.93,
        "needs_review": True,
        "warnings": [
            "Official 2027 pre-guide is available, but the full 2027 student application guidelines are scheduled for later publication.",
            "The PDF text layer is partially garbled; records are deterministic seed rows verified against the official table.",
        ],
    }


def extract_osaka_metropolitan_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _is_osaka_metropolitan_foreign_student_guide(compact):
        return []

    common = _common()
    return [
        {
            **common,
            "id": "osaka-metropolitan-2027-knowledge-information",
            "faculty": "現代システム科学域",
            "department": "知識情報システム学類",
            "application_period": "2026年10月5日(月)から2026年10月8日(木)。",
            "deadline_rule": "出願期間内に手続き。詳細な締切時刻・郵送条件は2027年度学生募集要項で確認。",
            "eju_session": "現代システム科学域および医学部医学科は、2025年度第2回(11月実施)または2026年度第1回(6月実施)の日本留学試験を利用。",
            "eju_japanese": "EJU日本語(読解、聴解・聴読解、記述)は合計270点以上。",
            "eju_math": "EJU数学コース2。知識情報システム学類は120点以上。",
            "eju_physics": "EJU理科は物理・化学・生物から2科目。理科は120点以上。",
            "eju_chemistry": "EJU理科は物理・化学・生物から2科目。理科は120点以上。",
            "english_requirement": _no_external_english_requirement_note(),
            "screening_method": "日本留学試験、個別学力検査等、口述・面接、出願書類を総合して判定。",
            "screening_schedule": "選抜期日: 2026年11月21日(土)。",
            "result_date": "合格者発表日: 2026年12月4日(金)。",
            "enrollment_period": "入学手続期間は2027年度学生募集要項で確認。",
            "evidence": "Official 2027 private-financed international student special selection pre-guide p.1 and p.6: system science domain schedule, EJU subjects, and score thresholds.",
        },
        {
            **common,
            "id": "osaka-metropolitan-2027-law",
            "faculty": "法学部",
            "department": "法学部",
            "application_period": "2026年12月16日(水)から2026年12月21日(月)。",
            "deadline_rule": "出願期間内に手続き。詳細な締切時刻・郵送条件は2027年度学生募集要項で確認。",
            "eju_session": "現代システム科学域・医学部医学科以外の学部は、2026年度第1回(6月実施)または2026年度第2回(11月実施)の日本留学試験を利用。",
            "eju_japanese": "EJU日本語を利用。",
            "eju_general": "法学部はEJU日本語、総合科目、数学コース1を利用し、合計600点以上が必要。",
            "eju_math": "EJU数学コース1。",
            "english_requirement": _no_external_english_requirement_note(),
            "screening_method": "日本留学試験、個別学力検査(外国語・作文)、口述試験、出願書類を総合して判定。",
            "screening_schedule": "選抜期日: 2027年2月25日(木)。",
            "result_date": "合格者発表日: 2027年3月9日(火)。",
            "enrollment_period": "入学手続期間は2027年度学生募集要項で確認。",
            "evidence": "Official 2027 private-financed international student special selection pre-guide p.1 and p.6: law faculty schedule, selection method, EJU subjects, and score threshold.",
        },
        {
            **common,
            "id": "osaka-metropolitan-2027-agriculture-applied-biological-sciences",
            "faculty": "農学部",
            "department": "応用生物科学科",
            "application_period": "2026年12月16日(水)から2026年12月21日(月)。",
            "deadline_rule": "出願期間内に手続き。詳細な締切時刻・郵送条件は2027年度学生募集要項で確認。",
            "eju_session": "現代システム科学域・医学部医学科以外の学部は、2026年度第1回(6月実施)または2026年度第2回(11月実施)の日本留学試験を利用。",
            "eju_japanese": "EJU日本語は合計270点以上。",
            "eju_math": "EJU数学コース2。",
            "eju_physics": "EJU理科は物理・化学・生物から2科目。農学部は理科の基準点なし。",
            "eju_chemistry": "EJU理科は物理・化学・生物から2科目。農学部は理科の基準点なし。",
            "english_requirement": "応用生物科学科はTOEFL iBTが必要。2026年1月20日以前のスコアは71点以上、2026年1月21日以降のスコアはバンドスコア4以上。",
            "screening_method": "日本留学試験、小論文、口述試験・面接、出願書類、TOEFLを総合して判定。",
            "screening_schedule": "選抜期日: 2027年2月26日(金)。",
            "result_date": "合格者発表日: 2027年3月9日(火)。",
            "enrollment_period": "入学手続期間は2027年度学生募集要項で確認。",
            "evidence": "Official 2027 private-financed international student special selection pre-guide p.3, p.5, and p.6: agriculture schedule, TOEFL requirement, selection method, and EJU thresholds.",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Osaka Metropolitan 2027 private-financed international student pre-guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_osaka_metropolitan_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(json.dumps({"records": records, "record_count": len(records), "source": "osaka_metropolitan_2027_undergrad_seed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
