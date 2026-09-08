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

SOURCE_URL = "https://www.kyushu-u.ac.jp/f/63057/R8_shihi_inst.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _application_period() -> str:
    return (
        "出願書類の郵送期間は2025年11月4日(火)から11月14日(金)17時必着。"
        "Web入力及び入学検定料の支払は2025年10月27日(月)から11月7日(金)17時まで。"
    )


def _deadline_rule() -> str:
    return (
        "インターネット出願はWeb入力と入学検定料支払いだけでは完了しない。"
        "必要な出願書類等を速達・書留郵便で郵送する必要がある。"
        "日本国外から出願する場合はEMS等の配達状況が確認可能な国際郵便で郵送する。"
    )


def _eligibility() -> str:
    return (
        "日本国以外の国籍を有する者で、日本国の永住許可を得ていない者。"
        "外国において学校教育における12年の課程を修了した者又は2026年3月31日までに修了見込みの者等。"
        "各学部が指定する2024年度又は2025年度の日本留学試験を受験し、"
        "TOEFL iBT、IELTS、IELTS Online(農学部以外)又はケンブリッジ英検を出願前2年以内に受験した者。"
    )


def _required_documents() -> str:
    return (
        "身上記録書、志望理由書又は経歴書(共創学部志願者のみ)、入学検定料納付領収書等、"
        "卒業証明書及び成績証明書、TOEFL等の成績証明書、日本留学試験の成績通知書写し又は成績確認書、"
        "旅券(パスポート)のコピー、在留カード又は住民票の写し等を提出。"
    )


def _eju_session() -> str:
    return (
        "2024年度第1回、2024年度第2回、2025年度第1回又は2025年度第2回の日本留学試験を利用。"
        "成績利用を希望する年度・回は一つ選び、出願後の変更はできない。出題言語は日本語・英語のいずれでもよい。"
    )


def _english_requirement() -> str:
    return (
        "TOEFL iBT(Home Editionを含む)、IELTS(アカデミック・モジュール)、IELTS Online(農学部以外)、"
        "又はケンブリッジ英検(FCE、CAE、CPE)のいずれかを出願前2年以内(2024年1月以降)に受験した成績証明書を提出。"
        "TOEFLはTest Dateスコアのみを活用し、MyBestスコアは活用しない。共創学部では自宅受験型の英語能力試験は認めない。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "result_date": "合格者発表: 2026年3月3日(火)11時頃。Web掲載は同日12時頃予定。",
        "enrollment_period": "入学手続は2026年3月4日(水)13時から3月15日(日)17時までに入学料納付とWeb入学手続を完了する。",
    }


def _base_record() -> dict[str, Any]:
    schedule = _common_schedule()
    return {
        "source_pdf": "kyushu_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "九州大学",
        "admission_year": "2026",
        "application_period": _application_period(),
        "deadline_rule": _deadline_rule(),
        "eligibility": _eligibility(),
        "required_documents": _required_documents(),
        "eju_session": _eju_session(),
        "english_requirement": _english_requirement(),
        "result_date": schedule["result_date"],
        "enrollment_period": schedule["enrollment_period"],
        "evidence": (
            "令和8年度(2026年度)九州大学私費外国人留学生入試(4月入学)学生募集要項: "
            "日程 p.2 / 出願資格・EJU指定表 p.3-p.4 / 募集人員 p.4-p.5 / "
            "出願手続 p.5-p.12 / 選抜方法・試験日時 p.13 / 合格発表 p.16 / 入学手続 p.17"
        ),
        "confidence": 0.97,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Kyushu University 2026 privately financed international undergraduate admissions guide."
        ],
    }


def extract_kyushu_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["九州大学", "私費外国人留学生入試", "学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "IELTS", "入学者選抜方法"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "kyushu-2026-literature",
            "faculty": "文学部",
            "department": "文学部",
            "eju_japanese": "文学部は日本留学試験の日本語を必須科目として指定。",
            "eju_general": "文学部は総合科目を必須科目として指定。",
            "eju_math": "文学部は数学コース1を必須科目として指定。",
            "screening_method": "TOEFL等の成績証明書、日本留学試験の成績、本学実施の日本語試験、出願書類、面接により選抜する。",
            "screening_schedule": "文学部は2026年2月26日(木)に日本語試験(読解・記述10:00-11:20、聴解11:50-12:35)、2月27日(金)10:00から面接。",
        },
        {
            **base,
            "id": "kyushu-2026-economics-engineering",
            "faculty": "経済学部",
            "department": "経済工学科",
            "eju_japanese": "経済学部経済工学科は日本語を必須科目として指定。",
            "eju_math": "経済学部経済工学科は数学コース2を必須科目として指定。",
            "eju_physics": "経済学部経済工学科は理科2科目選択で物理を選択可能。",
            "eju_chemistry": "経済学部経済工学科は理科2科目選択で化学を選択可能。",
            "eju_biology": "経済学部経済工学科は理科2科目選択で生物を選択可能。",
            "screening_method": "TOEFL等の成績証明書、日本留学試験の成績、本学実施の日本語試験、出願書類、面接により選抜する。",
            "screening_schedule": "経済学部は2026年2月26日(木)に日本語試験、2月27日(金)10:00から面接。",
        },
        {
            **base,
            "id": "kyushu-2026-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語を必須科目として指定し、読解・聴解・聴読解350点以上が出願基準点。",
            "eju_math": "医学部医学科は数学コース2を必須科目として指定。",
            "eju_physics": "医学部医学科は理科2科目選択で物理を選択可能。数学と理科の合計360点以上が出願基準点。",
            "eju_chemistry": "医学部医学科は理科2科目選択で化学を選択可能。数学と理科の合計360点以上が出願基準点。",
            "eju_biology": "医学部医学科は理科2科目選択で生物を選択可能。数学と理科の合計360点以上が出願基準点。",
            "screening_method": "TOEFL等の成績証明書、日本留学試験の成績、本学実施の日本語試験、出願書類、面接により選抜する。面接で基礎的な学力について試験を行うことがある。",
            "screening_schedule": "医学部医学科は2026年2月26日(木)に日本語試験、2月27日(金)9:00から面接。",
        },
        {
            **base,
            "id": "kyushu-2026-engineering",
            "faculty": "工学部",
            "department": "電気情報工学科 / 材料工学科 / 応用化学科 / 化学工学科 / 融合基礎工学科 / 機械工学科 / 航空宇宙工学科 / 量子物理工学科 / 船舶海洋工学科 / 地球資源システム工学科 / 土木工学科 / 建築学科",
            "eju_japanese": "工学部は日本語を必須科目として指定し、読解・聴解・聴読解300点以上が出願基準点。",
            "eju_math": "工学部は数学コース2を必須科目として指定。数学の出願基準点はなし。",
            "eju_physics": "工学部は理科で物理を必須科目として指定。理科の出願基準点はなし。",
            "eju_chemistry": "工学部は理科で化学を必須科目として指定。理科の出願基準点はなし。",
            "screening_method": "TOEFL等の成績証明書、日本留学試験の成績、出願書類、面接により選抜する。理学部・工学部・芸術工学部は本学実施の日本語試験を課さない。",
            "screening_schedule": "工学部は2026年2月27日(金)に面接。電気情報工学科・機械工学科・航空宇宙工学科は9:00から、その他の工学部学科・コースは11:00から。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Kyushu University 2026 international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_kyushu_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "kyushu_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
