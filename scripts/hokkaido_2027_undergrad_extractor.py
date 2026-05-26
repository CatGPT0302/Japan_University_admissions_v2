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

SOURCE_URL = "https://www.hokudai.ac.jp/admission/R9_shihi_kihonhoushin.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common_application_period() -> str:
    return (
        "インターネット出願登録および検定料支払い期間: 令和8(2026)年9月7日(月)10時から"
        "令和8(2026)年9月17日(木)17時まで。出願書類の郵送期間: "
        "令和8(2026)年9月14日(月)から令和8(2026)年9月18日(金)17時まで、期間内必着。"
    )


def _common_deadline_rule() -> str:
    return (
        "インターネット出願登録と検定料支払い後に出願書類の郵送が必要。"
        "郵送書類は令和8(2026)年9月18日(金)17時までに期間内必着。"
        "配達担当郵便局への到着時期によっては間に合わない場合があるため余裕をもって発送する。"
    )


def _common_eligibility() -> str:
    return (
        "日本の国籍を有しない者、かつ日本国の永住許可を得ていない者。"
        "外国において学校教育における12年の課程を修了した者又は令和9(2027)年3月31日までに"
        "修了見込みの者等。出願資格の一部区分では外国の学校において最終学年を含む2年以上"
        "継続して在学したことも要件。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "screening_schedule": "第1次選考結果発表: 令和8(2026)年10月27日(火)16時予定。第2次選考日: 令和8(2026)年11月15日(日)。",
        "result_date": "合格発表日: 令和8(2026)年12月8日(火)16時予定。",
        "enrollment_period": "入学手続期間: 令和8(2026)年12月8日(火)から令和8(2026)年12月14日(月)17時まで。",
    }


def _common_required_documents() -> str:
    return (
        "出願書類は郵送が必要。基本方針では選抜日程、出願資格、日本留学試験、英語能力試験、"
        "学部別選抜方法を示す。正式な提出書類一式は募集要項本文で確認する必要がある。"
    )


def _common_eju_session() -> str:
    return (
        "有効な日本留学試験は本学出願前2年以内の令和6(2024)年11月、令和7(2025)年6月、"
        "令和7(2025)年11月、令和8(2026)年6月。複数回の試験スコアを組み合わせることはできない。"
    )


def _general_eju_threshold() -> str:
    return (
        "上記以外の募集単位は、日本語の得点(記述を含む)270点以上、基礎科目"
        "(文系は総合科目と数学、理系は理科と数学)265点以上。"
    )


def _general_english_requirement() -> str:
    return (
        "学部別選抜方法で英語能力試験の成績通知書等の提出を課す。対象例はTOEFL、TOEIC L&R、"
        "国連英検、ケンブリッジ英検、実用英語技能検定試験(日本・英検)、IELTS、又は同等と"
        "認められる英語能力の検定試験。"
    )


def _base_record() -> dict[str, Any]:
    return {
        "source_pdf": "hokkaido_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "北海道大学",
        "admission_year": "2027",
        "application_period": _common_application_period(),
        "deadline_rule": _common_deadline_rule(),
        "eligibility": _common_eligibility(),
        "required_documents": _common_required_documents(),
        "eju_session": _common_eju_session(),
        "screening_schedule": _common_schedule()["screening_schedule"],
        "result_date": _common_schedule()["result_date"],
        "enrollment_period": _common_schedule()["enrollment_period"],
        "evidence": (
            "令和9(2027)年度私費外国人留学生(学部)入試基本方針: 募集人員 p.1-p.2 / "
            "選抜日程 p.2 / 出願資格及び要件 p.2-p.3 / 選抜方法 p.4-p.9 / EJU指定科目 別表 p.10"
        ),
        "confidence": 0.97,
        "needs_review": True,
        "warnings": [
            "Official Hokkaido University 2027 basic policy seed; final application guideline may add detailed document forms or procedural notes."
        ],
    }


def extract_hokkaido_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["令和9(2027)年度", "私費外国人留学生", "入試基本方針"]):
        return []
    if not _has_all(compact, ["日本留学試験", "出願期間", "第2次選考日", "別表"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "hokkaido-2027-literature",
            "faculty": "文学部",
            "department": "文学部",
            "eju_japanese": _general_eju_threshold(),
            "eju_general": "別表で文学部は日本語、総合科目、数学(コース1又はコース2)を指定。理科は不要。",
            "eju_math": "数学はコース1又はコース2。",
            "english_requirement": "文学部はTOEFL-iBT(Home Edition可)の成績提出を課す。",
            "screening_method": (
                "大学入学共通テストを免除。第1次選考は出願書類。第2次選考は課題論文、面接、"
                "日本留学試験及び最終修了学校の成績証明書等を総合して選考。"
            ),
        },
        {
            **base,
            "id": "hokkaido-2027-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語の得点(記述を含む)385点以上。",
            "eju_math": "医学部医学科は基礎科目(理科と数学)340点以上。数学はコース2。",
            "eju_physics": "別表で医学部医学科は理科の物理・化学を指定。",
            "eju_chemistry": "別表で医学部医学科は理科の物理・化学を指定。",
            "english_requirement": (
                "医学部医学科はTOEFL-iBT又はTOEIC L&Rを受験し、TOEFL-iBT(Home Edition可、"
                "Test Dateスコアに限る)79点以上、TOEIC L&R 750点以上。"
            ),
            "screening_method": (
                "大学入学共通テストを免除。第1次選考は出願書類。第2次選考は課題論文、面接、"
                "日本留学試験及び最終修了学校の成績証明書等を総合して選考。"
            ),
        },
        {
            **base,
            "id": "hokkaido-2027-engineering",
            "faculty": "工学部",
            "department": "応用理工系学科 / 情報エレクトロニクス学科 / 機械知能工学科 / 環境社会工学科",
            "eju_japanese": _general_eju_threshold(),
            "eju_math": "別表で工学部は数学コース2を指定。",
            "eju_physics": "応用物理工学、情報エレクトロニクス、機械知能、環境社会は化学・生物から1科目と物理。応用化学、応用マテリアルは物理・化学。",
            "eju_chemistry": "応用化学、応用マテリアルは物理・化学。その他の工学部募集単位は化学・生物から1科目と物理。",
            "english_requirement": _general_english_requirement(),
            "screening_method": (
                "大学入学共通テストを免除。第1次選考は出願書類。第2次選考は面接を行い、"
                "日本留学試験及び最終修了学校の成績証明書等の結果を総合して選考。"
            ),
        },
        {
            **base,
            "id": "hokkaido-2027-agriculture",
            "faculty": "農学部",
            "department": "農学部",
            "eju_japanese": "農学部は日本語の得点(記述を含む)340点以上。",
            "eju_math": "農学部は基礎科目(理科と数学)300点以上。数学はコース2。",
            "eju_physics": "別表で農学部は理科の物理・化学・生物から2科目を指定。",
            "eju_chemistry": "別表で農学部は理科の物理・化学・生物から2科目を指定。",
            "eju_biology": "別表で農学部は理科の物理・化学・生物から2科目を指定。",
            "english_requirement": _general_english_requirement(),
            "screening_method": (
                "大学入学共通テストを免除。第1次選考は出願書類。第2次選考は課題論文、面接、"
                "日本留学試験及び最終修了学校の成績証明書等を総合して選考。"
            ),
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Hokkaido University 2027 undergraduate international admissions basic policy.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_hokkaido_2027_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "hokkaido_2027_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
