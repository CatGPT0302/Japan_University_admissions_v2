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

SOURCE_URL = "https://ac.web.kit.ac.jp/02/nyushi/yoko/gakubu/2027_shihi_yoko.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "kyoto_institute_tech_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "京都工芸繊維大学",
        "admission_year": "2027",
        "application_period": "出願期間は2026 年 7 月 28 日（火）から2026 年 8 月 3 日（月）（日本時間）まで。",
        "deadline_rule": "簡易書留・速達等で期間内に大学へ届くことが必要。2026 年 8 月 3 日（月）までの日本国内消印は有効。海外から出願を検討している人は2026 年 7 月 17 日（金）までに入試課へ申し出る。",
        "eligibility": "日本国籍を有しないこと。2025 年 11 月又は2026 年 6 月実施の日本留学試験を受験していること。TOEFL iBTを2024 年 8 月から2026 年 6 月までに受験していること。外国で12 年の学校教育課程を修了又は2027 年 3 月 31 日までに修了見込みであること等。入学時までに留学又は大学入学に支障のない在留資格が必要。",
        "required_documents": "入学願書 / 履歴書 / 日本留学試験受験票（写） / TOEFLiBT スコアカード Test Taker Score Report / 出願資格区分に応じた証明書等 / 授業料免除申請書類（該当者） / 在留カード（写）（所持者） / 宛名ラベル",
        "eju_session": "2025 年 11 月又は2026 年 6 月実施の日本留学試験。両方受験した場合はいずれか1つを選択。",
        "eju_japanese": "日本語必須。日本語（聴解・読解・聴読解の400点満点中）280 点以上。記述の 50 点は含みません。",
        "eju_math": "数学（コース 2）必須。200点満点中120 点以上。",
        "english_requirement": "TOEFL（Home Editionを含むiBTテストのみ可）。2024 年 8 月から2026 年 6 月までの受験分が有効。TOEFL-ITPは不可。Test Dateスコアのみを使用し、My Bestスコアは使用しない。",
        "screening_method": "大学入学共通テストを免除し、日本留学試験の成績、TOEFLのスコア、本学が行う小論文・面接の結果を総合して選抜。",
        "screening_schedule": "全課程: 2026 年 8 月 25 日（火）10：00～11：30（90分）小論文、13：00～面接。",
        "result_date": "合格者発表は2026 年9 月 2 日（水）16 時（予定）。",
        "enrollment_period": "入学手続期間は2026 年 9 月 4 日（金）から2026 年 9 月 10 日（木）（17 時必着）まで。",
        "confidence": 0.98,
        "needs_review": True,
        "warnings": [
            "Deterministic seed extraction from Kyoto Institute of Technology 2027 privately financed international student undergraduate guideline; extend rows by human review."
        ],
    }


def extract_kit_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["京都工芸繊維大学", "2027", "私費外国人留学生入試"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "小論文", "面接"]):
        return []

    common = _common()
    return [
        {
            **common,
            "id": "kit-2027-applied-biology",
            "faculty": "応用生物学域",
            "department": "応用生物学課程",
            "eju_physics": "理科は物理・化学・生物から 2 科目を選択。",
            "eju_chemistry": "理科は物理・化学・生物から 2 科目を選択。",
            "evidence": "募集人員・EJU科目: p.1 / 日本語・数学点数、TOEFL、出願資格: p.2 / 出願書類・出願期間: p.3-p.4 / 選抜方法・試験日時: p.7 / 合格発表・入学手続: p.8",
        },
        {
            **common,
            "id": "kit-2027-applied-chemistry",
            "faculty": "物質・材料科学域",
            "department": "応用化学課程",
            "eju_physics": "理科は物理が必須。",
            "eju_chemistry": "理科は化学が必須。",
            "evidence": "募集人員・EJU科目: p.1 / 日本語・数学点数、TOEFL、出願資格: p.2 / 出願書類・出願期間: p.3-p.4 / 選抜方法・試験日時: p.7 / 合格発表・入学手続: p.8",
        },
        {
            **common,
            "id": "kit-2027-electronic-systems",
            "faculty": "設計工学域",
            "department": "電子システム工学課程",
            "eju_physics": "理科は物理が必須。",
            "eju_chemistry": "理科は化学・生物から 1 科目を選択。",
            "evidence": "募集人員・EJU科目: p.1 / 日本語・数学点数、TOEFL、出願資格: p.2 / 出願書類・出願期間: p.3-p.4 / 選抜方法・試験日時: p.7 / 合格発表・入学手続: p.8",
        },
        {
            **common,
            "id": "kit-2027-design-architecture",
            "faculty": "デザイン科学域",
            "department": "デザイン・建築学課程（建築コース / デザインコース）",
            "eju_physics": "理科は物理・化学・生物から 1 科目を選択。",
            "eju_chemistry": "理科は物理・化学・生物から 1 科目を選択。",
            "screening_method": common["screening_method"] + " デザイン・建築学課程の面接では、建築やデザインにかかわる作品等がある場合に内容説明を求められる。",
            "evidence": "募集人員・EJU科目: p.1 / 日本語・数学点数、TOEFL、出願資格: p.2 / 出願書類・出願期間: p.3-p.4 / 選抜方法・作品説明: p.7 / 合格発表・入学手続: p.8",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from KIT 2027 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_kit_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(
        json.dumps({"records": records, "record_count": len(records), "source": "kyoto_institute_tech_2027_undergrad_seed"}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
