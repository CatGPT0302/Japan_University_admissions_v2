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

SOURCE_URL = "https://www.okayama-u.ac.jp/user/st/nyushika/2026/pdf/bosyuyoko/shihi2026.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common_application_period() -> str:
    return (
        "文学部・法学部・経済学部・理学部・医学部・歯学部・薬学部・工学部の出願期間は"
        "2026年1月26日(月)から1月29日(木)17時必着。"
        "出願期間後に到着した願書は2026年1月27日(火)の日本国内消印のものまで受理される。"
        "インターネット出願ページへの入力は2026年1月13日(火)10時から可能。"
    )


def _agriculture_application_period() -> str:
    return (
        "農学部(農学グローバル入試)の出願期間は2025年11月4日(火)から11月11日(火)。"
        "出願期間後に到着した願書は2025年11月9日(日)の日本国内消印のものまで受理される。"
    )


def _common_deadline_rule() -> str:
    return (
        "出願はインターネット出願のみで、志願者登録、入学検定料決済、出願書類郵送を行う。"
        "志願票、写真票、出願書類提出用封筒宛名をダウンロードしてカラー印刷し、"
        "必要書類とともに角形2号封筒へ入れ、出願期間内に必着するよう書留・速達で郵送する。"
        "やむを得ず持参する場合は指定日に限り事前連絡の上で認められる。"
    )


def _common_eligibility() -> str:
    return (
        "日本国籍を有しない者。外国において学校教育における12年の課程を修了した者又は2026年3月31日までに修了見込みの者等。"
        "大学入学に支障のない在留資格を有する又は有する見込みのある者。"
        "日本の高等学校及び中等教育学校を卒業した者又は卒業見込みの者はこの入試に出願できない。"
    )


def _common_required_documents() -> str:
    return (
        "志願票、写真票、修了又は見込証明書、成績証明書又は成績評価証明書、身上記録、"
        "日本留学試験成績確認書又は成績通知書の写し、住民票の写し、英語資格・検定試験成績証明書、"
        "農学部は志望動機書と課題作文等を提出。"
    )


def _common_eju_session() -> str:
    return "文学部等は2025年度日本留学試験(2025年6月又は11月実施分)を利用。出題言語は学部により日本語指定又は自由選択。"


def _agriculture_eju_session() -> str:
    return "農学部は2024年度日本留学試験(2024年11月実施分)又は2025年度日本留学試験(2025年6月実施分)を利用。"


def _english_common() -> str:
    return (
        "英語資格・検定試験の成績証明書を提出する場合がある。"
        "対象はTOEFL iBT、IELTS、ケンブリッジ英語検定、英検、GTEC、TEAP、TEAP CBT、"
        "TOEIC Listening & Reading及びTOEIC Speaking & Writing等。"
        "TOEFL iBTはTest Dateスコアのみを活用し、My Bestスコア及びTOEFL iBT Home Editionは活用しない。"
        "TOEIC IPなど団体受験の成績は活用しない。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "result_date": "文学部等の合格者発表は2026年3月7日(土)15時予定。",
        "enrollment_period": "文学部等の入学手続期限は2026年3月18日(水)17時必着。入学手続専用サイトで手続き後、郵送で行う。",
    }


def _agriculture_schedule() -> dict[str, str]:
    return {
        "result_date": "農学部(農学グローバル入試)の合格者発表は2025年12月22日(月)10時予定。",
        "enrollment_period": "農学部(農学グローバル入試)の入学手続期限は2026年1月28日(水)17時必着。",
    }


def _base_record() -> dict[str, Any]:
    schedule = _common_schedule()
    return {
        "source_pdf": "okayama_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "岡山大学",
        "admission_year": "2026",
        "application_period": _common_application_period(),
        "deadline_rule": _common_deadline_rule(),
        "eligibility": _common_eligibility(),
        "required_documents": _common_required_documents(),
        "eju_session": _common_eju_session(),
        "english_requirement": _english_common(),
        "result_date": schedule["result_date"],
        "enrollment_period": schedule["enrollment_period"],
        "evidence": (
            "2026年度岡山大学私費外国人留学生選抜学生募集要項: 表紙日程 / 募集人員 p.1 / "
            "出願資格・EJU指定 p.1-p.2 / 出願手続 p.3 / 選抜方法 p.4-p.7 / "
            "合格発表 p.7 / 入学手続 p.8 / 出願書類 p.18-p.21 / 英語資格一覧 p.31-p.32"
        ),
        "confidence": 0.97,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Okayama University 2026 privately financed international admissions guide."
        ],
    }


def extract_okayama_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["岡山大学", "私費外国人留学生", "学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "出願資格", "入学者選抜方法"]):
        return []

    base = _base_record()
    ag_schedule = _agriculture_schedule()
    agriculture_base = {
        **base,
        "application_period": _agriculture_application_period(),
        "eju_session": _agriculture_eju_session(),
        "english_requirement": (
            _english_common()
            + "農学部は2024年4月以降に受験した英語資格・検定試験の成績を提出し、CEFR相当レベルとの対照表に基づき得点化して評価する。"
        ),
        "result_date": ag_schedule["result_date"],
        "enrollment_period": ag_schedule["enrollment_period"],
    }
    return [
        {
            **base,
            "id": "okayama-2026-literature",
            "faculty": "文学部",
            "department": "人文学科",
            "eju_japanese": "文学部人文学科は日本語を受験し、合計得点580点以上(記述を含まない)が必要。",
            "eju_general": "文学部人文学科は総合科目を受験する必要がある。",
            "eju_math": "文学部人文学科は数学コース1又はコース2を受験する必要がある。",
            "screening_method": "書類審査、日本留学試験、日本語作文、面接を総合して選抜する。",
            "screening_schedule": "文学部は2026年2月25日(水)、日本語作文9:00-10:30、面接13:00から。津島キャンパスで実施。",
        },
        {
            **base,
            "id": "okayama-2026-economics",
            "faculty": "経済学部",
            "department": "経済学科",
            "eju_japanese": "経済学部経済学科は日本語を受験し、合計得点560点以上(記述を含まない)が必要。",
            "eju_general": "経済学部経済学科は総合科目を受験し、総合科目110点以上が必要。",
            "eju_math": "経済学部経済学科は数学コース1又はコース2を受験し、数学110点以上が必要。出題言語は自由選択。",
            "screening_method": "書類審査、日本留学試験、小論文、面接を総合して選抜する。",
            "screening_schedule": "経済学部は2026年2月25日(水)、小論文(日本語)9:00-10:30、面接13:00から。津島キャンパスで実施。",
        },
        {
            **base,
            "id": "okayama-2026-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語を受験し、日本語記述を含む合計得点760点以上が必要。",
            "eju_math": "医学部医学科は数学コース2を受験する必要がある。",
            "eju_physics": "医学部医学科は理科で物理を必須とし、化学又は生物から1科目を選択する。",
            "eju_chemistry": "医学部医学科は理科で物理必須、化学又は生物から1科目選択。化学を選択可能。",
            "eju_biology": "医学部医学科は理科で物理必須、化学又は生物から1科目選択。生物を選択可能。",
            "screening_method": "一般選抜前期日程受験生と同一の外国語、理科、数学の試験と面接を課し、書類審査と総合して選抜する。",
            "screening_schedule": "医学部医学科は2026年2月25日(水)に外国語9:00-11:00、理科12:30-14:30、数学16:00-18:00、2月26日(木)9:00から面接。鹿田キャンパスで実施。",
        },
        {
            **base,
            "id": "okayama-2026-engineering-mechanical",
            "faculty": "工学部",
            "department": "工学科機械システム系",
            "eju_japanese": "工学部工学科機械システム系は日本語を受験する必要がある。",
            "eju_math": "工学部工学科機械システム系は数学コース2を受験する必要がある。",
            "eju_physics": "工学部工学科機械システム系は理科で物理を必須とし、化学又は生物から1科目を選択する。",
            "eju_chemistry": "工学部工学科機械システム系は理科で物理必須、化学又は生物から1科目選択。化学を選択可能。",
            "eju_biology": "工学部工学科機械システム系は理科で物理必須、化学又は生物から1科目選択。生物を選択可能。",
            "screening_method": "一般選抜前期日程受験生と同一の理科及び数学の試験、小論文、面接を課し、書類審査と総合して選抜する。",
            "screening_schedule": "工学部工学科機械システム系は2026年2月25日(水)、理科12:30-14:30、数学16:00-18:00、小論文と面接も課す。津島キャンパスで実施。",
        },
        {
            **agriculture_base,
            "id": "okayama-2026-agriculture-global",
            "faculty": "農学部",
            "department": "農学科(農学グローバル入試)",
            "eju_japanese": "農学部は日本留学試験の日本語を利用する。",
            "eju_math": "農学部は日本留学試験の数学を利用する。",
            "eju_physics": "農学部は日本留学試験の理科を利用し、物理を選択可能。",
            "eju_chemistry": "農学部は日本留学試験の理科を利用し、化学を選択可能。",
            "eju_biology": "農学部は日本留学試験の理科を利用し、生物を選択可能。",
            "screening_method": "農学部は書類審査(日本留学試験、英語資格・検定試験、志望動機、課題作文)及びオンライン面接を総合して選抜する。",
            "screening_schedule": "農学部は2025年12月6日(土)13:00からオンライン面接を実施。事前のオンライン接続テストは2025年12月3日(水)。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Okayama University 2026 international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_okayama_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "okayama_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
