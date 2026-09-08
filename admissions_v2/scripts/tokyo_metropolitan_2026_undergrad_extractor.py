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

SOURCE_URL = "https://www.tmu.ac.jp/extra/download.html?d=assets%2Ffiles%2Fdownload%2Fentrance%2F2026_tsg_bosyuuyoukou.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _application_period() -> str:
    return "出願期間: 2025年12月4日(木)から12月8日(月)20時郵送必着。"


def _deadline_rule() -> str:
    return (
        "インターネット出願はマイページ登録、顔写真登録、出願登録、入学考査料支払、志願票等印刷、"
        "必要書類郵送を出願期間終了までにすべて行う。登録及び支払だけでは出願完了にならない。"
        "書留速達又は外国からEMS等で郵送し、郵便遅配は考慮しない。"
    )


def _eligibility() -> str:
    return (
        "外国人で、外国において正規の学校教育における12年の課程を修了した者又は2026年3月31日までに"
        "修了見込みの者等。日本の中学校・高等学校等に在籍していた場合は通算3年以内かつ12年目を外国の学校で"
        "修了した者に限る。"
    )


def _required_documents() -> str:
    return (
        "志願票、出願資格に係る卒業証明書等及び成績証明書等、日本語訳、日本留学試験の成績確認書又は"
        "受験票コピー、外部英語検定試験の成績証明書等、外国籍を証明する書類を提出。"
    )


def _eju_session() -> str:
    return "2024年度又は2025年度実施の日本留学試験が対象。出題言語は日本語。日本語は記述を除く得点を採用。"


def _english_common(kind: str) -> str:
    return (
        f"{kind}を受験し、出願期間までに本学へスコアが到着するよう手続する。"
        "各種試験の自宅受験版スコアは認めない。TOEFL iBTを課す学科ではTest Dateスコアのみ有効でMyBestスコアは活用しない。"
    )


def _base_record() -> dict[str, Any]:
    return {
        "source_pdf": "tokyo_metropolitan_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "東京都立大学",
        "admission_year": "2026",
        "application_period": _application_period(),
        "deadline_rule": _deadline_rule(),
        "eligibility": _eligibility(),
        "required_documents": _required_documents(),
        "eju_session": _eju_session(),
        "result_date": "第1次選抜結果発表: 2026年2月11日(水)正午。最終合格発表日: 2026年3月8日(日)正午。",
        "enrollment_period": "入学手続期間: 2026年3月10日(火)から3月15日(日)郵送必着。入学時期は2026年4月。",
        "evidence": (
            "2026年度東京都立大学私費外国人留学生入試学生募集要項: 日程 p.1 / "
            "募集人員・資格 p.3-p.4 / 出願手続・書類 p.4-p.8 / 選抜方法 p.9-p.10 / "
            "入学手続 p.10-p.11 / 学力試験 p.12-p.14 / EJU別表 p.15"
        ),
        "confidence": 0.97,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Tokyo Metropolitan University 2026 privately financed international admissions guide."
        ],
    }


def extract_tokyo_metropolitan_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["東京都立大学", "私費外国人留学生入試", "学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "TOEFL", "出願期間", "別表4"]):
        return []

    base = _base_record()
    return [
        {
            **base,
            "id": "tokyo-metropolitan-2026-humanities",
            "faculty": "人文社会学部",
            "department": "人間社会学科 / 人文学科",
            "eju_japanese": "人文社会学部は日本語を指定。日本語400点配点で、本学では記述を除く得点を採用。",
            "eju_general": "人文社会学部は総合科目を指定。",
            "eju_math": "人文社会学部は数学コース指定なし。",
            "english_requirement": _english_common("TOEFL iBT"),
            "screening_method": "第1次選抜は日本留学試験及びTOEFL iBTの成績。第2次選抜は小論文と面接。",
            "screening_schedule": "小論文: 2026年2月25日(水)15:00-16:30。面接: 2026年3月3日(火)13:00から。",
        },
        {
            **base,
            "id": "tokyo-metropolitan-2026-law",
            "faculty": "法学部",
            "department": "法学科",
            "eju_japanese": "法学部は日本語を指定。日本語400点配点で、本学では記述を除く得点を採用。",
            "eju_general": "法学部は総合科目を指定。",
            "eju_math": "法学部は数学コース指定なし。",
            "english_requirement": _english_common("TOEFL iBT"),
            "screening_method": "第1次選抜は日本留学試験成績。第2次選抜は地理歴史1科目選択と面接(日本語による簡単な作文を含む)。",
            "screening_schedule": "地理歴史: 2026年2月25日(水)12:30-14:00。面接: 2026年3月3日(火)11:00から。",
        },
        {
            **base,
            "id": "tokyo-metropolitan-2026-physics",
            "faculty": "理学部",
            "department": "物理学科",
            "eju_japanese": "理学部物理学科は日本語を指定。日本語400点配点で、本学では記述を除く得点を採用。",
            "eju_math": "理学部物理学科は数学コース2を指定。",
            "eju_physics": "理学部物理学科は理科で物理、化学の2科目指定。",
            "eju_chemistry": "理学部物理学科は理科で物理、化学の2科目指定。",
            "english_requirement": _english_common("TOEFL iBT又はIELTSアカデミック・モジュール"),
            "screening_method": "第1次選抜は日本留学試験成績。第2次選抜は数学、理科、面接(口頭試問を含む)。",
            "screening_schedule": "数学: 2026年2月26日(木)10:00-11:15。理科: 14:45-16:00。面接: 2026年3月3日(火)13:00から。",
        },
        {
            **base,
            "id": "tokyo-metropolitan-2026-mechanical",
            "faculty": "システムデザイン学部",
            "department": "機械システム工学科",
            "eju_japanese": "システムデザイン学部機械システム工学科は日本語を指定。日本語400点配点で、本学では記述を除く得点を採用。",
            "eju_math": "機械システム工学科は数学コース2を指定。",
            "eju_physics": "機械システム工学科は理科で物理を指定し、化学又は生物から1科目選択の計2科目。",
            "eju_chemistry": "機械システム工学科は物理のほか、化学又は生物から1科目選択。",
            "eju_biology": "機械システム工学科は物理のほか、化学又は生物から1科目選択。",
            "english_requirement": _english_common("TOEIC L&R/S&W、TOEFL iBT又はIELTSアカデミック・モジュール"),
            "screening_method": "第1次選抜は日本留学試験成績。第2次選抜は数学、理科、面接(口頭試問を含む)。",
            "screening_schedule": "数学: 2026年2月26日(木)10:00-11:15。理科: 14:45-16:00。面接: 2026年3月3日(火)13:00から。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Tokyo Metropolitan University 2026 international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_tokyo_metropolitan_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "tokyo_metropolitan_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
