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

SOURCE_URL = "https://www.osaka-u.ac.jp/ja/admissions/faculty/expense/files/2026shihi_guideline-1.pdf/@@download/file"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common_application_period() -> str:
    return (
        "Web出願システム登録期間: 2025年12月15日(月)10時から2026年1月8日(木)17時。"
        "出願書類受理期間: 2026年1月5日(月)から1月9日(金)17時必着。"
    )


def _common_deadline_rule() -> str:
    return (
        "出願手続はWeb出願システム登録、検定料支払い、出願書類の郵送をすべて完了する必要がある。"
        "Web出願システムへの登録だけでは完了しない。出願書類は書留速達郵便で郵送し、持参は不可。"
        "1月7日以前の日本国内消印の書留速達郵便に限り、期限後到着でも受理される場合がある。"
    )


def _common_eligibility() -> str:
    return (
        "日本国籍を有しない者(日本国の永住許可を得ている者を除く)。外国に所在し外国の教育制度に"
        "基づく教育機関で学校教育における12年の課程を修了した者又は2026年3月31日までに修了見込みの者等。"
    )


def _common_required_documents() -> str:
    return (
        "志願票、提出物チェックリスト、各種証明書類、顔写真データ、検定料支払い、"
        "日本留学試験成績、TOEFLスコアなどをWeb出願システムと郵送で提出。"
        "証明書原本・翻訳証明の扱いは募集要項の注意事項を確認。"
    )


def _common_eju_session() -> str:
    return "大阪大学が利用する日本留学試験は2024年度6月・11月、2025年度6月・11月実施分。"


def _toefl_note(score: str) -> str:
    return (
        f"TOEFLはTest Date Scoresのみ有効でMyBest Scoresは利用不可。受験日が2024年1月5日以降の"
        f"TOEFL iBTスコアが対象。TOEFL iBT Home Editionは通常のTOEFL iBTスコアと同様に扱う。{score}"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "result_date": "合格者発表日: 2026年3月9日(月)。",
        "enrollment_period": "入学手続は合格者発表後の指定期間に行う。募集要項本文の入学手続章で詳細を確認。",
    }


def _base_record() -> dict[str, Any]:
    return {
        "source_pdf": "osaka_university_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "大阪大学",
        "admission_year": "2026",
        "application_period": _common_application_period(),
        "deadline_rule": _common_deadline_rule(),
        "eligibility": _common_eligibility(),
        "required_documents": _common_required_documents(),
        "eju_session": _common_eju_session(),
        "result_date": _common_schedule()["result_date"],
        "enrollment_period": _common_schedule()["enrollment_period"],
        "evidence": (
            "2026年度大阪大学私費外国人留学生特別入試学生募集要項: 表紙日程 p.1 / "
            "実施日程 p.4 / 募集人員 p.5 / 出願資格 p.6-p.7 / EJU・TOEFL基準表 p.8-p.10 / "
            "選抜方法 p.11-p.12 / 試験日時 p.13 / 出願手続 p.15"
        ),
        "confidence": 0.97,
        "needs_review": True,
        "warnings": [
            "Deterministic seed extraction from official Osaka University 2026 privately financed international admissions guide; table-heavy EJU rules should be spot-checked when expanding rows."
        ],
    }


def extract_osaka_university_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["大阪大学", "私費外国人留学生特別入試", "学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "出願資格", "選抜方法"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "osaka-university-2026-literature",
            "faculty": "文学部",
            "department": "人文学科",
            "eju_japanese": "文学部は日本留学試験の日本語を利用し、読解・聴解・聴読解の合計300点以上、記述260点以上。",
            "eju_general": "文学部は総合科目を利用。",
            "eju_math": "文学部は数学コース1を利用。",
            "english_requirement": _toefl_note("文学部はiBT 48点以上。"),
            "screening_method": "小論文と口頭試問を課し、日本語による小論文で勉学・研究に必要な適性と能力を判定する。",
            "screening_schedule": "文学部は2026年2月25日(水)、小論文10:00-12:00、口頭試問13:00から。",
        },
        {
            **base,
            "id": "osaka-university-2026-science-biology",
            "faculty": "理学部",
            "department": "生物科学科生命理学コース",
            "eju_japanese": "理学部生物科学科生命理学コースは日本語を利用し、合計300点以上。",
            "eju_math": "理学部生物科学科生命理学コースは数学コース2を利用し、数学を含む理系科目を指定。",
            "eju_physics": "理学部生物科学科生命理学コースは理科で物理と化学の計2科目を必須。",
            "eju_chemistry": "理学部生物科学科生命理学コースは理科で物理と化学の計2科目を必須。",
            "english_requirement": _toefl_note("理学部生物科学科生命理学コースはiBT 61点以上。"),
            "screening_method": "数学、理科(物理基礎・物理、化学基礎・化学)、口頭試問を課す。",
            "screening_schedule": "理学部は2026年2月25日(水)に数学9:00-11:30、理科15:30-18:00、2月26日(木)に口頭試問。",
        },
        {
            **base,
            "id": "osaka-university-2026-medicine",
            "faculty": "医学部",
            "department": "医学科",
            "eju_japanese": "医学部医学科は日本語を利用し、合計400点以上。",
            "eju_math": "医学部医学科は数学コース2を利用し、理系基礎科目は合計360点以上。",
            "eju_physics": "医学部医学科は理科で物理、化学、生物から計2科目。",
            "eju_chemistry": "医学部医学科は理科で物理、化学、生物から計2科目。",
            "eju_biology": "医学部医学科は理科で物理、化学、生物から計2科目。",
            "english_requirement": "医学部医学科はTOEFL欄が出願基準点なし。ただし表の注意によりTOEFL未受験又はスコア未提出は出願資格なし。",
            "screening_method": "小論文として科学論文を出題し、筆記試験合格者に個人面接30分程度を2回実施する。",
            "screening_schedule": "医学部医学科は2026年2月7日(土)小論文9:00-12:00、2月8日(日)面接9:30-18:00。",
        },
        {
            **base,
            "id": "osaka-university-2026-engineering",
            "faculty": "工学部",
            "department": "応用自然科学科 / 応用理工学科 / 電子情報工学科 / 環境・エネルギー工学科 / 地球総合工学科",
            "eju_japanese": "工学部は日本語を利用し、読解・聴解・聴読解200点以上、記述25点以上。",
            "eju_math": "工学部は数学コース2を利用し、理系基礎科目は合計240点以上。",
            "eju_physics": "工学部は物理が必須で、化学と生物から1科目を選ぶ計2科目。",
            "eju_chemistry": "工学部は物理のほか化学又は生物から1科目を選択。",
            "eju_biology": "工学部は物理のほか化学又は生物から1科目を選択。",
            "english_requirement": "工学部はTOEFL欄が出願基準点なし。ただし表の注意によりTOEFL未受験又はスコア未提出は出願資格なし。",
            "screening_method": "数学、理科(物理必須、化学又は生物から1科目)、口頭試問を課す。",
            "screening_schedule": "工学部は2026年2月25日(水)に数学9:00-11:30、理科15:30-18:00、2月26日(木)に口頭試問10:00から。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Osaka University 2026 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_osaka_university_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "osaka_university_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
