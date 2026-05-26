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

SOURCE_URL = "https://ciec.kwansei.ac.jp/upload/ac1aedfe5e5ec128838c7e4a4cb47ea569d24597.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common_application_period() -> str:
    return (
        "第I期試験: 2026年8月24日(月) 9:00～8月31日(月) 23:00 / 郵送書類は8月31日(月)必着。"
        "第II期試験: 2026年11月16日(月) 9:00～11月24日(火) 23:00 / 郵送書類は11月24日(火)必着。"
    )


def _common_deadline_rule() -> str:
    return "郵送書類は第I期8月31日、第II期11月24日必着。日本国外から出願する場合は追跡確認ができる方法で送付し、郵便事情は考慮されません。"


def _common_eligibility() -> str:
    return (
        "外国籍を有する者。日本の学校教育法に基づく小学校・中学校・高等学校等に在学した期間が通算4年以内。"
        "外国において学校教育における12年の課程を修了した者、または2027年3月31日までに修了見込の者等。"
        "該当しない場合は出願開始日1カ月前までに個別の入学資格審査が必要。"
    )


def _common_documents(*, online_consent: bool, english: bool) -> str:
    documents = [
        "出願資格確認用紙",
        "入学志願調書",
        "出身高等学校の卒業(修了)証明書または卒業(修了)見込証明書",
        "出身高等学校の成績証明書",
        "日本留学試験(EJU)成績確認書/受験票コピー貼付用紙",
        "パスポートコピー貼付用紙",
        "志望理由書",
        "提出書類チェックシート",
    ]
    if english:
        documents.insert(5, "英語能力を証明する書類のコピー")
    if online_consent:
        documents.insert(-1, "オンライン面接に関する同意書")
    return " / ".join(documents)


def _common_eju_session(*, include_second_phase: bool) -> str:
    if include_second_phase:
        return "第I期試験: 2025年度第2回(11月)または2026年度第1回(6月)。第II期試験: 2025年度第2回(11月)、2026年度第1回(6月)、2026年度第2回(11月)。"
    return "第I期試験: 2025年度第2回(11月)または2026年度第1回(6月)。"


def _common_eju_japanese() -> str:
    return "EJU日本語は読解・聴解・聴読解の合計が第I期260点以上かつ記述30点以上、第II期265点以上かつ記述35点以上。ただし点数は目安で必須ではありません。"


def _common_english_requirement() -> str:
    return (
        "TOEIC(TOEIC IPを含む)、TOEFL(TOEFL ITP/TOEFL iBT)、IELTSのいずれか。"
        "スコア有効期限は第I期試験2024年8月24日以降実施分、第II期試験2024年11月16日以降実施分。"
        "TOEIC IPを除く自宅受験型の試験は対象としません。"
    )


def extract_kwansei_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["関西学院大学", "2027年度", "外国人留学生入学試験要項"]):
        return []
    if not _has_all(compact, ["第I期試験", "第II期試験", "日本留学試験", "出願資格", "提出書類"]):
        return []

    common = {
        "source_pdf": "kwansei_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "関西学院大学",
        "admission_year": "2027",
        "deadline_rule": _common_deadline_rule(),
        "eligibility": _common_eligibility(),
        "eju_japanese": _common_eju_japanese(),
        "evidence": "表紙: p.1 / 入試内容・面接方式: p.3-p.4 / 日程・出願資格・EJU共通要件: p.5-p.6 / 学部別EJU・英語要件・提出書類: p.7-p.9 / 合格発表・入学手続: p.17-p.19",
        "confidence": 0.98,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Kwansei Gakuin 2027 undergraduate international student admissions guide; extend by human review."],
    }

    return [
        {
            **common,
            "id": "kwansei-2027-literature",
            "faculty": "文学部",
            "department": "文化歴史学科 / 総合心理科学科 / 文学言語学科",
            "application_period": "第I期試験: 2026年8月24日(月) 9:00～8月31日(月) 23:00 / 郵送書類は8月31日(月)必着。",
            "required_documents": _common_documents(online_consent=False, english=False),
            "eju_session": _common_eju_session(include_second_phase=False),
            "eju_general": "EJU学部別要件: 日本語 / 総合科目。",
            "screening_method": "第一次審査はEJU成績を含めた提出書類による書類審査。第二次審査は提出書類に加え面接による審査。",
            "screening_schedule": "第I期試験の第二次審査試験日は2026年10月10日(土)。文学部は西宮上ケ原キャンパスで対面面接。",
            "result_date": "第一次審査合格者発表: 2026年9月25日(金) 9:00。合格発表: 2026年11月13日(金) 9:00。",
            "enrollment_period": "入学手続I: 2026年11月13日(金)～11月27日(金)。入学手続II: Web申請2027年2月15日(月)～3月4日(木)15:00、学費等納入2027年2月15日(月)～3月11日(木)。",
        },
        {
            **common,
            "id": "kwansei-2027-law",
            "faculty": "法学部",
            "department": "法律学科 / 政治学科",
            "application_period": _common_application_period(),
            "required_documents": _common_documents(online_consent=True, english=False),
            "eju_session": _common_eju_session(include_second_phase=True),
            "eju_general": "EJU学部別要件: 日本語 / 総合科目。",
            "english_requirement": "英語能力試験欄に○があるため、英語能力試験の受験が学部別要件に含まれます。",
            "screening_method": "第一次審査はEJU成績を含めた提出書類による書類審査。第二次審査は提出書類に加えオンライン面接による審査。",
            "screening_schedule": "第二次審査試験日: 第I期2026年10月10日(土)、第II期2027年1月16日(土)。法学部はオンライン面接。",
            "result_date": "第一次審査合格者発表: 第I期2026年9月25日(金) 9:00、第II期2027年1月8日(金) 9:00。合格発表: 第I期2026年11月13日(金) 9:00、第II期2027年1月22日(金) 9:00。",
            "enrollment_period": "入学手続I: 第I期2026年11月13日(金)～11月27日(金)、第II期2027年1月22日(金)～1月29日(金)。入学手続II: Web申請2027年2月15日(月)～3月4日(木)15:00、学費等納入2027年2月15日(月)～3月11日(木)。",
        },
        {
            **common,
            "id": "kwansei-2027-science",
            "faculty": "理学部",
            "department": "数理科学科 / 物理・宇宙学科 / 化学科",
            "application_period": _common_application_period(),
            "required_documents": _common_documents(online_consent=False, english=True),
            "eju_session": _common_eju_session(include_second_phase=True),
            "eju_math": "EJU学部別要件: 日本語 / 数学コース2。理・工・生命環境・建築学部の数学の出題言語は日本語または英語どちらでも可。",
            "eju_physics": "EJU理科は物理・化学・生物からいずれか2科目。物理・宇宙学科および化学科を志望する場合は物理・化学の2科目を選択。",
            "eju_chemistry": "EJU理科は物理・化学・生物からいずれか2科目。物理・宇宙学科および化学科を志望する場合は物理・化学の2科目を選択。",
            "english_requirement": _common_english_requirement(),
            "screening_method": "EJU成績を含めた提出書類による書類審査。試験場での選考はありません。",
            "screening_schedule": "理学部は試験場での選考はありません。",
            "result_date": "合格発表: 第I期2026年11月13日(金) 9:00、第II期2027年1月22日(金) 9:00。",
            "enrollment_period": "入学手続I: 第I期2026年11月13日(金)～11月27日(金)、第II期2027年1月22日(金)～1月29日(金)。入学手続II: Web申請2027年2月15日(月)～3月4日(木)15:00、学費等納入2027年2月15日(月)～3月11日(木)。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Kwansei Gakuin 2027 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_kwansei_2027_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "kwansei_2027_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
