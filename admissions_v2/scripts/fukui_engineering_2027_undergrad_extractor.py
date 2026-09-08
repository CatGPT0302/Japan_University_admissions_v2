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

SOURCE_URL = "https://www.u-fukui.ac.jp/wp/wp-content/uploads/bsy27_shihiryu_youkou.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "fukui_engineering_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "福井大学",
        "faculty": "工学部",
        "admission_year": "2027",
        "application_period": "出願期間は2026（令和8）年10 月 13 日（火）から10 月 20 日（火）16 時までに必着。",
        "deadline_rule": "出願書類は郵送（簡易書留速達）で2026 年10 月 20 日16 時までに必着。期限後到着でも2026 年10 月 19 日までの発信局日付印がある簡易書留速達郵便に限り受理。持参による出願は認めない。",
        "eligibility": "日本国籍を有しない者（日本国永住許可を得ている者を除く）。外国で12 年の課程を修了又は2027 年3 月31 日までに修了見込み等。2025 年度又は2026 年度日本留学試験の指定科目を受験し、2026 年度成績を利用する場合は第1回のみ対象。2025 年1 月以降実施のTOEFLを受験していること。留学の在留資格を有する又は入学時に取得見込みであること。",
        "required_documents": "入学志願票 / 誓約書（海外居住者でオンライン面接希望者） / 受験票・写真票 / 出願確認票 / 出願資格証明書及び成績証明書 / 外国語証明書の日本語訳 / 日本留学試験の受験票（写） / TOEFL のスコア票（Test Taker Score Report、Official Score Report） / 住民票等又はパスポートコピー / 在留資格に係る承諾書（該当者） / あて名票 / 返信用封筒 / 出願用封筒",
        "eju_session": "2025 年度又は2026 年度日本留学試験。2026 年度成績を利用する場合は第 1 回のみ対象。",
        "eju_japanese": "日本留学試験の日本語を課す。出題言語は日本語に限ります。",
        "eju_math": "日本留学試験の数学（コース２）を課す。",
        "eju_general": "日本留学試験の総合科目は課さない（×）。",
        "eju_physics": "日本留学試験の理科は物理・化学・生物から２科目。",
        "eju_chemistry": "日本留学試験の理科は物理・化学・生物から２科目。",
        "english_requirement": "TOEFLを課す。出願資格上は2025 年1 月以降実施分が必要。TOEFL iBT Home Editionも認める。Test Taker Score ReportとOfficial Score Reportの両方を提出。福井大学 DI コードは0184。スコア票は2024（令和6）年10 月以降実施分に限る。",
        "screening_method": "日本留学試験、TOEFL、本学が実施する面接等の成績及び出願書類を総合して選抜。面接及び口頭試問を実施。",
        "screening_schedule": "選考日は2026（令和8）年10 月 30 日（金）、福井大学文京キャンパス。13:00～13:15受付、13:30～面接及び口頭試問。海外居住者でオンライン希望者はオンラインで実施。",
        "result_date": "合格者発表は2026（令和8）年11 月 30 日（月）10 時。",
        "enrollment_period": "入学手続期間は2026（令和8）年12 月 14 日（月）から12 月 25 日（金）16 時までに必着。",
        "confidence": 0.98,
        "needs_review": True,
        "warnings": [
            "Deterministic seed extraction from University of Fukui 2027 Faculty of Engineering privately financed international student guideline; extend rows by human review."
        ],
    }


def extract_fukui_engineering_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["福井大学", "工学部", "私費外国人留学生選抜"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "面接", "口頭試問"]):
        return []

    common = _common()
    departments = [
        ("fukui-2027-mechanical-systems", "機械・システム工学科"),
        ("fukui-2027-electrical-electronic-information", "電気電子情報工学科"),
        ("fukui-2027-architecture-urban-environment", "建築・都市環境工学科"),
        ("fukui-2027-materials-life-chemistry", "物質・生命化学科"),
        ("fukui-2027-applied-physics", "応用物理学科"),
    ]
    return [
        {
            **common,
            "id": record_id,
            "department": department,
            "evidence": "日程概要: p.0 / 募集人員: p.6 / 出願資格: p.7 / 出願期間・出願書類: p.8-p.10 (p.9含む) / 選抜方法等: p.12 / 合格者発表・入学手続: p.13",
        }
        for record_id, department in departments
    ]


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return Path(args.text).read_text(encoding="utf-8")
    if args.pdf:
        pages = extract_text_per_page(args.pdf)
        return "\n".join(text for _page, text in sorted(pages.items()))
    raise ValueError("--text or --pdf is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from University of Fukui 2027 engineering international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_fukui_engineering_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(
        json.dumps({"records": records, "record_count": len(records), "source": "fukui_engineering_2027_undergrad_seed"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
