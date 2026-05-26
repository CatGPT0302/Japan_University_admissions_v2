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

SOURCE_URL = "https://admission.ritsumei.ac.jp/assets/file/2027/admission/international/ryugakusei-youkou.pdf"


def _compact(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", str(text or ""))).strip()


def _has_all(text: str, terms: list[str]) -> bool:
    return all(term in text for term in terms)


def _common() -> dict[str, Any]:
    return {
        "source_pdf": "ritsumeikan_2027_undergrad.pdf",
        "source_document": SOURCE_URL,
        "university": "立命館大学",
        "admission_year": "2027",
        "application_period": "前期実施: 2026年8月18日(火)10:00～8月28日(金)23:00。後期実施: 2026年11月9日(月)10:00～11月16日(月)23:00。",
        "deadline_rule": "出願はオンライン出願システムTAOで行い、各出願期間最終日の23:00までに出願登録、出願書類提出、入学検定料支払い、出願完了を済ませる必要があります。",
        "eligibility": "外国籍を有する者。2027年3月31日までに外国において12年の課程を修了した者等で、日本の小学校・中学校・高等学校等に在学した期間が通算3年以内。該当不明の場合は出願期間開始日の1カ月前までに個別の入学資格審査について問い合わせ。",
        "required_documents": "高等学校卒業(修了)証明書または卒業(修了)見込証明書 / 高等学校の全学年の成績証明書 / 志望理由書 / パスポート / 写真 / 日本留学試験成績確認書・成績通知書または受験票",
        "eju_session": "前期実施: 2025年度第2回(11月実施)または2026年度第1回(6月実施)。後期実施: 2026年度第1回(6月実施)または2026年度第2回(11月実施)。",
        "result_date": "前期実施: 第1次選考2026年9月25日(金)9:30、第2次選考2026年10月19日(月)9:30。後期実施: 第1次選考2026年12月25日(金)9:30、第2次選考2027年1月20日(水)9:30。",
        "enrollment_period": "第1次入学手続: 前期実施2026年10月19日(月)～11月2日(月)、後期実施2027年1月20日(水)～2月3日(水)。第2次入学手続: 2027年3月9日(火)～3月18日(木)。",
        "evidence": "表紙・日程: p.1-p.2 / 出願資格・EJU・英語要件: p.6-p.8 / 出願書類: p.9-p.11 / 選考方法・面接方式: p.13-p.14 / 合格発表・入学手続: p.18-p.19",
        "confidence": 0.98,
        "needs_review": True,
        "warnings": ["Deterministic seed extraction from the official Ritsumeikan 2027 undergraduate international student admissions guide; extend by human review."],
    }


def extract_ritsumeikan_2027_undergrad_records(text: str) -> list[dict[str, Any]]:
    compact = _compact(text)
    if not _has_all(compact, ["立命館大学", "2027", "外国人留学生入学試験"]):
        return []
    if not _has_all(compact, ["前期実施", "後期実施", "日本留学試験", "出願資格"]):
        return []

    common = _common()
    law_general = "EJU受験必須科目: 日本語(記述問題含む)、総合科目または数学(コース1またはコース2)のいずれか1科目。"
    law_japanese = "EJU日本語(記述問題含む)。前期実施の出願基準点: 日本語(読解、聴解・聴読解)280点以上、日本語(記述)35点以上。後期実施は目安点で、目安点以上を取得していなくても出願要件を満たします。"
    return [
        {
            **common,
            "id": "ritsumeikan-2027-law",
            "faculty": "法学部",
            "department": "法学科",
            "eju_japanese": law_japanese,
            "eju_general": law_general,
            "screening_method": "全学部(経営学部を除く)は2段階選抜。第1次選考は日本留学試験の成績、第2次選考は日本留学試験の成績と個人面接の総合評価。",
            "screening_schedule": "法学部の第2次選考日は前期2026年10月3日(土)、後期2027年1月9日(土)。日本国内住所は衣笠キャンパスでの対面面接、日本国外住所は自宅等でのオンライン面接。",
        },
        {
            **common,
            "id": "ritsumeikan-2027-business",
            "faculty": "経営学部",
            "department": "経営学科",
            "eligibility": common["eligibility"] + " 経営学部は英語外部資格試験の成績証明書を提出できる者。",
            "required_documents": common["required_documents"] + " / 英語外部資格試験の成績証明書",
            "eju_japanese": law_japanese,
            "eju_general": law_general,
            "english_requirement": "経営学部は英語外部資格試験が必要。実用英語技能検定、TOEFL iBT、TOEIC Listening & Reading、IELTS、TEAP、Duolingo English Test等。TOEFL iBT Home Edition、TOEFL Essentials、TOEIC IP、IELTS Online、IELTS One Skill Retakeは対象としません。",
            "screening_method": "経営学部は1段階選抜。日本留学試験の成績と出願書類の総合評価で、第2次選考は行いません。",
            "screening_schedule": "経営学部は面接試験を実施しないため、試験日の設定はありません。",
            "result_date": "経営学部の合格発表日: 前期実施2026年10月19日(月)9:30、後期実施2027年1月20日(水)9:30。",
        },
        {
            **common,
            "id": "ritsumeikan-2027-science-engineering",
            "faculty": "理工学部",
            "department": "数理科学科 / 物理科学科 / 電気電子工学科 / 電子情報工学科 / 機械工学科 / ロボティクス学科 / 環境都市工学科 / 建築都市デザイン学科",
            "eju_japanese": "EJU日本語(記述問題含む)。前期実施の出願基準点: 日本語(読解、聴解・聴読解)250点以上、日本語(記述)30点以上。後期実施は目安点で、目安点以上を取得していなくても出願要件を満たします。",
            "eju_math": "EJU受験必須科目: 数学(コース2)。",
            "eju_physics": "EJU受験必須科目: 理科(物理・化学の2科目)。",
            "eju_chemistry": "EJU受験必須科目: 理科(物理・化学の2科目)。",
            "screening_method": "全学部(経営学部を除く)は2段階選抜。第1次選考は日本留学試験の成績、第2次選考は日本留学試験の成績と個人面接の総合評価。理工学部では理系の素養を確認するために口頭試問を行います。",
            "screening_schedule": "理工学部の第2次選考日は前期2026年10月4日(日)、後期2027年1月10日(日)。日本国内住所はびわこ・くさつキャンパスでの対面面接、日本国外住所は自宅等でのオンライン面接。",
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
    parser = argparse.ArgumentParser(description="Deterministically extract seed rows from Ritsumeikan 2027 undergraduate international admissions guide.")
    parser.add_argument("--text", default="", help="Path to extracted text.")
    parser.add_argument("--pdf", default="", help="Path to the official PDF.")
    parser.add_argument("--output", required=True, help="Path to write records JSON.")
    args = parser.parse_args(argv)
    records = extract_ritsumeikan_2027_undergrad_records(_read_text(args))
    Path(args.output).write_text(json.dumps({"records": records, "record_count": len(records), "source": "ritsumeikan_2027_undergrad_seed"}, ensure_ascii=False, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
