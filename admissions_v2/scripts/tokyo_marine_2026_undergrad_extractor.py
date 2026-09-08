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

SOURCE_URL = "https://www.kaiyodai.ac.jp/upload-file/4bf4353ccc4bc6c8427eaad38d44488a88ab62ae.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _application_period() -> str:
    return (
        "出願期間: 2026年1月26日(月)から2月4日(水)17:00郵送必着。"
        "インターネット出願登録と検定料支払いは2026年1月23日(金)10:00から2月4日(水)16:00。"
    )


def _deadline_rule() -> str:
    return (
        "マイページ登録、インターネット出願登録、検定料支払いだけでは出願は完了しない。"
        "必要書類を出願期間内に書留速達郵便で郵送して大学へ提出することで完了する。"
        "大学への直接持参は受け付けない。"
    )


def _eligibility() -> str:
    return (
        "日本国籍を有しない者で、日本国永住許可を得ている者は除く。"
        "外国において学校教育における12年の課程を修了した者又は2026年3月31日までに修了見込みの者等。"
        "大学入学に支障のない在留資格を有する者又は受験の際に有する見込みの者。"
        "日本の高等学校又は中等教育学校を卒業した者・卒業見込みの者はこの入試に出願できない。"
    )


def _life_resource_documents() -> str:
    return (
        "入学志願票、英語資格検定証明書のコピー、志望理由書、最終学校の卒業証明書又は修了見込証明書、"
        "成績証明書、履歴書、日本語学校の成績証明書・在学証明書・卒業証明書又は出席日数証明、"
        "日本語学校推薦書、2025年度日本留学試験の成績確認書又は通知書、住民票又はパスポート写し、宛名ラベル等。"
    )


def _engineering_documents() -> str:
    return (
        "入学志願票、志望理由書、最終学校の卒業証明書又は修了見込証明書、成績証明書、履歴書、"
        "日本語学校の成績証明書・在学証明書・卒業証明書又は出席日数証明、"
        "日本語学校推薦書、2025年度日本留学試験の成績確認書又は通知書、住民票又はパスポート写し、"
        "海事システム工学科・海洋電子機械工学科志願者用の確認書、宛名ラベル等。"
    )


def _eju_session() -> str:
    return "2025年度に実施される日本留学試験を利用。出題言語は日本語で受験する必要がある。"


def _english_life_resource() -> str:
    return (
        "海洋生命科学部・海洋資源環境学部は英語資格等が出願要件。"
        "TOEIC L&R(TOEIC-IPを含む)400点以上、TOEFL iBT 40点以上(My Best Scoreを含む)又はTOEFL-ITP Level 1 435点以上、"
        "IELTS 3.5以上、GTEC 3技能又はGTEC for STUDENTS 500点以上(2019年3月31日まで)、GTEC 4技能830点以上、"
        "GTEC CBT 720点以上(2017年3月31日まで)、英検準2級以上、TEAP 4技能160点以上、"
        "TEAP CBT 4技能280点以上、ケンブリッジ英語検定120点以上のいずれか。"
        "TOEIC-IP、TOEFL-ITP、GTEC 3技能の団体受験は志願者の在籍校が実施団体の場合のみ認める。"
    )


def _common_schedule() -> dict[str, str]:
    return {
        "result_date": "合格発表日: 2026年3月9日(月)。",
        "enrollment_period": "入学手続期間: 2026年3月9日(月)から3月15日(日)。入学日は2026年4月1日(水)。",
    }


def _base_record() -> dict[str, Any]:
    schedule = _common_schedule()
    return {
        "source_pdf": "tokyo_marine_2026_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "東京海洋大学",
        "admission_year": "2026",
        "application_period": _application_period(),
        "deadline_rule": _deadline_rule(),
        "eligibility": _eligibility(),
        "eju_session": _eju_session(),
        "result_date": schedule["result_date"],
        "enrollment_period": schedule["enrollment_period"],
        "evidence": (
            "令和8(2026)年度東京海洋大学私費外国人留学生特別入試学生募集要項: "
            "日程 p.1 / 海洋生命科学部・海洋資源環境学部の募集・出願資格・EJU p.17 / "
            "英語資格 p.18-p.19 / 出願手続 p.19-p.22 / 入試方法 p.23-p.24 / "
            "海洋工学部の募集・出願資格・EJU p.25 / 出願要件・手続 p.26-p.28 / 入試方法 p.29-p.30"
        ),
        "confidence": 0.97,
        "needs_review": False,
        "warnings": [
            "Deterministic seed extraction from official Tokyo University of Marine Science and Technology 2026 privately financed international admissions guide."
        ],
    }


def _life_resource_record_base() -> dict[str, Any]:
    return {
        **_base_record(),
        "required_documents": _life_resource_documents(),
        "eju_japanese": "海洋生命科学部・海洋資源環境学部は日本留学試験の日本語を受験する必要がある。",
        "eju_math": "海洋生命科学部・海洋資源環境学部は数学コース2を受験する必要がある。",
        "eju_physics": "海洋生命科学部・海洋資源環境学部は理科から2科目選択。物理を選択可能。",
        "eju_chemistry": "海洋生命科学部・海洋資源環境学部は理科から2科目選択。化学を選択可能。",
        "eju_biology": "海洋生命科学部・海洋資源環境学部は理科から2科目選択。生物を選択可能。",
        "english_requirement": _english_life_resource(),
        "screening_method": (
            "大学入学共通テストを免除し、個別テスト、面接、日本留学試験の成績、提出書類を総合して判定する。"
            "出願要件としての英語資格検定資料は判定資料から除く。個別テストは日本語、英語、数学・物理・化学・生物から2科目選択。"
        ),
        "screening_schedule": (
            "2026年2月25日(水)、品川キャンパスで実施。10:00-12:00日本語・外国語、"
            "13:30-15:30数学又は理科、16:00から面接。"
        ),
    }


def extract_tokyo_marine_2026_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["東京海洋大学", "私費外国人留学生特別入試", "学生募集要項"]):
        return []
    if not _has_all(compact, ["日本留学試験", "出願期間", "英語資格", "海洋工学部"]):
        return []

    life_resource = _life_resource_record_base()
    base = _base_record()
    engineering = {
        **base,
        "id": "tokyo-marine-2026-marine-engineering",
        "faculty": "海洋工学部",
        "department": "海事システム工学科 / 海洋電子機械工学科 / 流通情報工学科",
        "required_documents": _engineering_documents(),
        "eju_japanese": "海洋工学部は日本留学試験の日本語を受験する必要がある。",
        "eju_math": "海洋工学部は数学コース2を受験する必要がある。",
        "eju_physics": "海洋工学部は理科で物理を受験する必要がある。",
        "eju_chemistry": "海洋工学部は理科で化学を受験する必要がある。",
        "english_requirement": "海洋工学部は英語資格・検定試験に係る出願要件は無し。",
        "screening_method": (
            "大学入学共通テストを免除し、個別テスト、面接、日本留学試験の成績、提出書類を総合して判定する。"
            "個別テストは数学と外国語(英語)。配点は数学300点、英語100点、面接200点、"
            "日本留学試験の数学100点、物理150点、化学150点、合計1000点。"
            "原則として個別テストと日本留学試験の得点合計600点以上の者を対象に総合判定する。"
        ),
        "screening_schedule": (
            "2026年2月25日(水)、越中島キャンパスで実施。10:00-12:00数学、"
            "13:30-14:00外国語、14:30から面接。"
        ),
    }

    return [
        {
            **life_resource,
            "id": "tokyo-marine-2026-marine-bioresources",
            "faculty": "海洋生命科学部",
            "department": "海洋生物資源学科",
        },
        {
            **life_resource,
            "id": "tokyo-marine-2026-food-science",
            "faculty": "海洋生命科学部",
            "department": "食品生産科学科",
        },
        {
            **life_resource,
            "id": "tokyo-marine-2026-marine-environment",
            "faculty": "海洋資源環境学部",
            "department": "海洋環境科学科",
        },
        engineering,
    ]


def _read_text(args: argparse.Namespace) -> str:
    if args.text:
        return Path(args.text).read_text(encoding="utf-8")
    if args.pdf:
        pages = extract_text_per_page(args.pdf)
        return "\n".join(text for _page, text in sorted(pages.items()))
    raise ValueError("--text or --pdf is required")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Tokyo University of Marine Science and Technology 2026 international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)

    records = extract_tokyo_marine_2026_undergrad_records(_read_text(args))
    payload = {"records": records, "record_count": len(records), "source": "tokyo_marine_2026_undergrad_seed"}
    Path(args.output).write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
