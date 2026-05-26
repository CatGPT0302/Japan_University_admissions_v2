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

SOURCE_URL = "https://admissions.tohoku.ac.jp/ja/adcms/wp-content/uploads/2025/12/r8shihi.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common_application_period() -> str:
    return (
        "出願受付期間: 2026年2月2日(月)から2月5日(木)正午必着。"
        "TAO出願サイトは令和8年(2026年)1月3日(土)午前10時予定から事前登録可能だが、"
        "郵送受付は出願受付期間に限る。"
    )


def _common_deadline_rule() -> str:
    return (
        "TAO出願サイトでの出願、入学検定料の納入を経て、出願期間内に必要な出願書類を"
        "速達・簡易書留郵便で本学に郵送して完了。出願登録と入学検定料納入だけでは出願完了にならない。"
        "出願書類は2026年2月5日(木)正午必着で、持参は受け付けない。"
    )


def _common_eligibility() -> str:
    return (
        "日本国籍を有しない者で、在留資格が留学である者又は入学時に留学の在留資格を取得見込みの者。"
        "日本国との多重国籍者及び日本国の永住許可を得ている者は出願不可。外国において学校教育における"
        "12年の課程を修了した者等で、2026年3月31日までの該当見込みを含む。"
    )


def _common_required_documents() -> str:
    return (
        "入学志願書、写真票、高等学校等の卒業(見込)証明書、成績証明書、日本留学試験成績通知書の写し"
        "又は成績確認書、TOEFL TESTのスコアシート、旅券の写し、日本在住者は住民票、入学検定料納付証明。"
        "日本語又は英語以外の証明書は和訳又は英訳を添付。"
    )


def _common_eju_session() -> str:
    return "2025年度(令和7年度)日本留学試験の6月実施分又は11月実施分が対象。"


def _common_english_requirement() -> str:
    return (
        "2024年3月1日以降にTOEFL iBT TESTを受験し、得点79点以上。Test Dateスコアのみ利用し、"
        "MyBestスコアは利用しない。Home Editionの提出も認める。TOEFL ITPは不可。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "screening_schedule": "受験票印刷可能日: 2026年2月12日(木)。試験実施: 2026年3月10日(火)。",
        "result_date": "合格者発表: 2026年3月18日(水)午後5時。",
        "enrollment_period": "入学手続期間: 2026年3月24日(火)から3月27日(金)必着。入学時期は2026年4月。",
    }


def _base_record() -> dict[str, Any]:
    return {
        "source_pdf": "tohoku_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "東北大学",
        "admission_year": "2026",
        "application_period": _common_application_period(),
        "deadline_rule": _common_deadline_rule(),
        "eligibility": _common_eligibility(),
        "required_documents": _common_required_documents(),
        "eju_session": _common_eju_session(),
        "english_requirement": _common_english_requirement(),
        "screening_schedule": _common_schedule()["screening_schedule"],
        "result_date": _common_schedule()["result_date"],
        "enrollment_period": _common_schedule()["enrollment_period"],
        "evidence": (
            "令和8年度東北大学私費外国人留学生入試学生募集要項: 表紙日程 p.1 / "
            "募集人員 p.7-p.8 / 出願資格・EJU・TOEFL p.9 / 選抜方法 p.10 / "
            "出願手続 p.11-p.15 / 試験日時 p.17"
        ),
        "confidence": 0.98,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Tohoku University 2026 privately financed international undergraduate admissions guide."
        ],
    }


def extract_tohoku_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["令和8年度", "東北大学", "私費外国人留学生入試"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL iBT", "出願資格", "出願書類"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "tohoku-2026-literature",
            "faculty": "文学部",
            "department": "人文社会学科",
            "eju_japanese": "文学部は日本語(記述得点を含む)380点以上。",
            "eju_general": "文学部は文系の試験科目。日本語、総合科目、数学コース1を指定し、基礎学力290点以上。",
            "eju_math": "文学部は数学コース1。",
            "screening_method": (
                "出願書類、日本留学試験、本学が実施する面接試験の結果を総合して選抜。"
                "文学部は学力試験を実施しない。面接は2026年3月10日10:00から。"
            ),
        },
        {
            **base,
            "id": "tohoku-2026-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語(記述得点を含む)380点以上。",
            "eju_math": "医学部医学科は理系の試験科目。数学コース2を指定し、基礎学力350点以上。",
            "eju_physics": "医学部医学科は理科(物理、化学、生物から2科目自由選択)を指定。",
            "eju_chemistry": "医学部医学科は理科(物理、化学、生物から2科目自由選択)を指定。",
            "eju_biology": "医学部医学科は理科(物理、化学、生物から2科目自由選択)を指定。",
            "screening_method": (
                "出願書類、日本留学試験、本学が実施する面接試験の結果を総合して選抜。"
                "医学部医学科は学力試験を実施しない。面接は2026年3月10日10:00から。"
            ),
        },
        {
            **base,
            "id": "tohoku-2026-engineering",
            "faculty": "工学部",
            "department": "機械知能・航空工学科 / 電気情報物理工学科 / 化学・バイオ工学科 / 材料科学総合学科 / 建築・社会環境工学科",
            "eju_japanese": "工学部は日本語(記述得点を含む)270点以上。",
            "eju_math": "工学部は理系の試験科目。数学コース2を指定し、基礎学力320点以上。",
            "eju_physics": "工学部は理科の物理、化学の2科目を指定。",
            "eju_chemistry": "工学部は理科の物理、化学の2科目を指定。",
            "screening_method": (
                "出願書類、日本留学試験、本学が実施する面接試験の結果を総合して選抜。"
                "工学部は学力試験を実施しない。面接は2026年3月10日10:00から。"
            ),
        },
        {
            **base,
            "id": "tohoku-2026-agriculture",
            "faculty": "農学部",
            "department": "生物生産科学科 / 応用生物化学科",
            "eju_japanese": "農学部は日本語(記述得点を含む)270点以上。",
            "eju_general": "農学部は理系の試験科目。基礎学力260点以上。",
            "eju_math": "農学部は数学コース2を指定。",
            "eju_physics": "農学部は理科(物理、化学、生物から2科目自由選択)を指定。",
            "eju_chemistry": "農学部は理科(物理、化学、生物から2科目自由選択)を指定。",
            "eju_biology": "農学部は理科(物理、化学、生物から2科目自由選択)を指定。",
            "screening_method": (
                "出願書類、日本留学試験、本学が実施する学力試験及び面接試験の結果を総合して選抜。"
                "農学部は数学の学力試験を9:30-11:00、面接を13:00から実施。"
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Tohoku University 2026 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_tohoku_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "tohoku_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
