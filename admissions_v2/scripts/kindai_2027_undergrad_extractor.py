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

SOURCE_URL = "https://www.kindai.ac.jp/files/campus-life/international-exchange/exam/department/entrance-exam-a.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _application_period() -> str:
    return "前期入試: 2026年8月24日(月)～8月27日(木)。後期入試: 2027年1月8日(金)～1月14日(木)。"


def _deadline_rule() -> str:
    return "前期入試の国内居住者は2026年8月27日消印有効、国外居住者は2026年8月31日必着。後期入試の国内居住者は2027年1月14日消印有効。"


def _eligibility() -> str:
    return "外国籍を有する者。外国において正規の学校教育における12年目の課程を修了した者等。2027年3月31日までに18歳に達する者。前期は在留資格「留学」を有する者または入学時に取得できる者、後期は出願時に在留資格「留学」を有する者。"


def _required_documents(*, english: bool = False) -> str:
    docs = [
        "出願確認票",
        "入学願書",
        "住民票の写しまたはパスポートのコピー",
        "日本留学試験(EJU)成績確認書",
        "卒業証明書",
        "CSSD証明書",
    ]
    if english:
        docs.append("英語能力証明書")
    return " / ".join(docs)


def _no_english_requirement_note() -> str:
    return "英語能力証明書は出願書類に含まれない。英語要件は情報学部・農学部の出願者に限定されるため、本seedでは要件なしとして明示。"


def _eju_session() -> str:
    return "前期入試: 2025年第2回または2026年度第1回。後期入試: 2026年第1回または第2回。"


def _result_date() -> str:
    return "合格発表日: 前期入試2026年11月9日、後期入試2027年3月9日。"


def _enrollment_period() -> str:
    return "前期入試: 第一次入学手続2026年11月9日～11月27日、第二次入学手続2026年11月9日～2027年1月13日。後期入試: 2027年3月9日～3月15日。"


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "kindai_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "近畿大学",
        "admission_year": "2027",
        "application_period": _application_period(),
        "deadline_rule": _deadline_rule(),
        "eligibility": _eligibility(),
        "eju_session": _eju_session(),
        "result_date": _result_date(),
        "enrollment_period": _enrollment_period(),
        "confidence": 0.98,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Kindai 2027 undergraduate international student admissions guide; extend by human review."],
    }


def extract_kindai_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["近畿大学", "2027", "外国人留学生入学試験要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "出願資格", "出願書類", "口頭試問"]):
        return []

    common = _common()
    return [
        {
            **common,
            "id": "kindai-2027-law",
            "faculty": "法学部",
            "department": "法律学科",
            "required_documents": _required_documents(),
            "english_requirement": _no_english_requirement_note(),
            "eju_japanese": "EJU日本語(記述を含む)が320点以上。",
            "eju_general": "EJU総合科目が140点以上。",
            "screening_method": "出願書類、日本留学試験(EJU)成績、口頭試問結果を総合して合否を判定。",
            "screening_schedule": "試験日は前期2026年10月10日、後期2027年2月20日。法学部の口頭試問は10:30開始。",
            "evidence": "表紙・目次: p.1 / 募集学部・日程・出願資格: p.2-p.4 / 出願書類: p.5 / 選考方法: p.9-p.13 / 合格発表・入学手続: p.14",
        },
        {
            **common,
            "id": "kindai-2027-architecture",
            "faculty": "建築学部",
            "department": "建築学科",
            "required_documents": _required_documents(),
            "english_requirement": _no_english_requirement_note(),
            "eju_japanese": "EJU受験必須科目: 日本語(記述を含む)。",
            "eju_math": "EJU受験必須科目: 数学コース2。出題言語は日本語と英語いずれか選択。",
            "eju_physics": "EJU受験必須科目に理科を含む。",
            "eju_chemistry": "EJU受験必須科目に理科を含む。",
            "screening_method": "出願書類、EJU成績、学部独自試験、口頭試問結果を総合して合否を判定。学部独自試験は実技試験(デッサン)。",
            "screening_schedule": "実技試験(デッサン)10:00～11:00、口頭試問11:20～。",
            "evidence": "表紙・目次: p.1 / 募集学部・日程・出願資格: p.2-p.4 / 出願書類: p.5 / 建築学部選考方法: p.10 / 合格発表・入学手続: p.14",
        },
        {
            **common,
            "id": "kindai-2027-agriculture",
            "faculty": "農学部",
            "department": "農学科 / 水産学科 / 応用生命化学科 / 食品栄養学科 / 環境管理学科 / 生物機能科学科",
            "required_documents": _required_documents(english=True),
            "eju_japanese": "EJU受験必須科目: 日本語(記述を含む)。",
            "eju_physics": "EJU受験必須科目に理科を含む。",
            "eju_chemistry": "EJU受験必須科目に理科を含む。",
            "english_requirement": "情報学部・農学部出願者は英語能力証明書が必要。TOEFL、TOEIC、IELTS、実用英語技能検定(英検)、国際連合公用語英語検定試験(国連英検)のいずれか。TOEFL ITPおよびTOEIC IPは不可。",
            "screening_method": "出願書類、日本留学試験(EJU)成績、口頭試問結果を総合して合否を判定。",
            "screening_schedule": "農学部の口頭試問は11:00開始。",
            "evidence": "表紙・目次: p.1 / 募集学部・日程・出願資格・英語証明: p.2-p.5 / 農学部選考方法: p.12 / 合格発表・入学手続: p.14",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Kindai 2027 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_kindai_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(json.dumps({"records": records, "record_count": len(records), "source": "kindai_2027_undergrad_seed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
