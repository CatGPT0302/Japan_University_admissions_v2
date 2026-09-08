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

SOURCE_URL = "https://www.nagoya-u.ac.jp/admissions/exam/upload/2026_shihi_yoko.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _application_period() -> str:
    return (
        "インターネット出願登録期間及び入学検定料払込期間は2025年11月24日(月)10時から12月4日(木)15時。"
        "出願書類郵送期間は2025年12月1日(月)から12月5日(金)15時郵送必着。"
    )


def _deadline_rule() -> str:
    return (
        "出願完了にはSakSakでの出願登録、入学検定料支払い、必要書類の郵送が必要。"
        "出願書類の提出は郵送(簡易書留・速達郵便)に限る。"
        "海外から出願する場合は国際郵便等の専用封筒に入れて志望学部へ送付する。"
    )


def _eligibility() -> str:
    return (
        "日本国籍を有しない者。日本国籍との多重国籍者及び日本国の永住許可を得ている者は出願できない。"
        "外国において学校教育における12年の課程を修了した者又は2026年3月31日までに修了見込みの者等。"
        "日本の高等学校又は対応する学校の課程を卒業した者・卒業見込みの者は出願が認められない。"
    )


def _required_documents() -> str:
    return (
        "志願票・写真票、履歴書、出願資格証明書、卒業又は修了証明書、学業成績証明書、"
        "日本留学試験の成績通知書又は成績確認書と受験票のコピー、TOEFL又はIELTSの成績証明書、"
        "在留カード両面コピー又は国籍及び在留資格を確認できるもの、必要に応じてオンライン面接受験誓約書や志願理由・特別課題を提出。"
    )


def _eju_session() -> str:
    return (
        "2024年度第2回又は2025年度第1回の日本留学試験を利用。"
        "受験科目の出題言語は日本語を選択して受験する必要がある。"
    )


def _english_common() -> str:
    return (
        "TOEFL又はIELTS(Academic Module)を出願開始日前2年以内(2023年12月1日から2025年11月30日)に受験し、"
        "学部・学科指定の得点を取得する必要がある。TOEFL-ITPは利用不可。"
        "TOEFL iBT Home EditionはTOEFL iBTと同様に扱い、農学部を除きMy Bestスコアを利用する。"
        "IELTS Onlineも同様に取り扱い、One Skill Retakeによるスコアを利用できる。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "result_date": "合格者発表: 2026年2月11日(水)12時。",
        "enrollment_period": "入学手続期間: 2026年2月11日(水)から2月18日(水)15時まで。",
    }


def _base_record() -> dict[str, Any]:
    schedule = _common_schedule()
    return {
        "source_pdf": "nagoya_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "名古屋大学",
        "admission_year": "2026",
        "application_period": _application_period(),
        "deadline_rule": _deadline_rule(),
        "eligibility": _eligibility(),
        "required_documents": _required_documents(),
        "eju_session": _eju_session(),
        "english_requirement": _english_common(),
        "result_date": schedule["result_date"],
        "enrollment_period": schedule["enrollment_period"],
        "evidence": (
            "2026年度名古屋大学私費外国人留学生募集要項: 募集人員 p.15 / 日程 p.16 / "
            "出願資格・EJU要件 p.17-p.18 / 英語要件 p.19 / 選抜方法 p.20-p.21 / "
            "出願手続・書類 p.22-p.30 / 合格発表・入学手続 p.33"
        ),
        "confidence": 0.97,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Nagoya University 2026 privately financed international admissions guide; engineering is not represented because the guide lists no engineering recruitment."
        ],
    }


def extract_nagoya_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["名古屋大学", "私費外国人留学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "IELTS", "出願資格及び要件"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "nagoya-2026-literature",
            "faculty": "文学部",
            "department": "文学部",
            "eju_japanese": "文学部は日本語を受験し、読解・聴解・聴読解220点以上が必要。",
            "eju_general": "文学部は総合科目を受験し、総合科目と数学コース1の合計265点以上が必要。",
            "eju_math": "文学部は数学コース1を受験し、総合科目と数学コース1の合計265点以上が必要。",
            "english_requirement": _english_common() + "文学部はTOEFL iBT 61点以上又はIELTS 5.5以上。",
            "screening_method": "日本留学試験、TOEFL又はIELTS、名古屋大学が実施する小論文・面接、出願書類により総合的に選抜する。",
            "screening_schedule": "文学部は2026年1月30日(金)、小論文10:00-11:00、面接13:00-17:00。試験は対面で実施。",
        },
        {
            **base,
            "id": "nagoya-2026-informatics-natural",
            "faculty": "情報学部",
            "department": "自然情報学科",
            "eju_japanese": "情報学部自然情報学科は日本語を受験し、記述・読解・聴解・聴読解300点以上が必要。",
            "eju_math": "情報学部自然情報学科は数学コース2を受験し、理科と数学コース2の合計265点以上が必要。",
            "eju_physics": "情報学部自然情報学科は理科で物理・化学・生物から2科目選択。物理を選択可能。",
            "eju_chemistry": "情報学部自然情報学科は理科で物理・化学・生物から2科目選択。化学を選択可能。",
            "eju_biology": "情報学部自然情報学科は理科で物理・化学・生物から2科目選択。生物を選択可能。",
            "english_requirement": _english_common() + "情報学部はTOEFL iBT 61点以上。",
            "screening_method": "情報学部は第1次選考を出願書類で行い、第1次選考合格者に第2次選考としてオンライン面接を実施する。",
            "screening_schedule": "情報学部は2025年12月23日(火)17時に第1次選考結果発表。2026年1月30日(金)にオンライン面接を実施し、詳細時間は合格者へ別途通知。",
        },
        {
            **base,
            "id": "nagoya-2026-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語を受験し、記述・読解・聴解・聴読解420点以上が必要。",
            "eju_math": "医学部医学科は数学コース2を受験し、理科と数学コース2の合計380点以上が必要。",
            "eju_physics": "医学部医学科は理科で物理・化学・生物から2科目選択。物理を選択可能。",
            "eju_chemistry": "医学部医学科は理科で物理・化学・生物から2科目選択。化学を選択可能。",
            "eju_biology": "医学部医学科は理科で物理・化学・生物から2科目選択。生物を選択可能。",
            "english_requirement": _english_common() + "医学部医学科はTOEFL iBT 90点以上。",
            "screening_method": "医学部医学科は日本留学試験、TOEFL、筆記試験、面接、出願書類により総合的に選抜する。筆記は生命科学を中心として日本語で出題。",
            "screening_schedule": "医学部医学科は2026年1月30日(金)、筆記13:00-14:00、面接14:30から。鶴舞地区で対面実施。",
        },
        {
            **base,
            "id": "nagoya-2026-agriculture",
            "faculty": "農学部",
            "department": "生物環境科学科 / 資源生物科学科 / 応用生命科学科",
            "eju_japanese": "農学部は日本語を受験し、記述・読解・聴解・聴読解300点以上が必要。",
            "eju_math": "農学部は数学コース2を受験し、理科と数学コース2の合計300点以上が必要。",
            "eju_physics": "農学部は理科で物理・化学・生物から2科目選択。物理を選択可能。",
            "eju_chemistry": "農学部は理科で物理・化学・生物から2科目選択。化学を選択可能。",
            "eju_biology": "農学部は理科で物理・化学・生物から2科目選択。生物を選択可能。",
            "english_requirement": _english_common() + "農学部はTOEFL iBT 61点以上。農学部ではMy Bestスコアを利用しない。",
            "screening_method": "農学部は日本留学試験、TOEFL、提出書類、小論文、口頭試問を含む面接で総合的に評価する。",
            "screening_schedule": "農学部は2026年1月30日(金)、小論文10:00-10:45、面接13:00から。東山地区で対面実施。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Nagoya University 2026 international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_nagoya_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "nagoya_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
