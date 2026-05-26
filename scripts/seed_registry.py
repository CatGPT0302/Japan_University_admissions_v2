from __future__ import annotations

from typing import Any, Callable

from scripts.chukyo_gakuin_2027_undergrad_extractor import extract_chukyo_gakuin_2027_undergrad_records
from scripts.fukui_engineering_2027_undergrad_extractor import extract_fukui_engineering_2027_undergrad_records
from scripts.hokkaido_2027_undergrad_extractor import extract_hokkaido_2027_undergrad_records
from scripts.keio_medicine_2027_extractor import extract_keio_2027_medicine_records
from scripts.kindai_2027_undergrad_extractor import extract_kindai_2027_undergrad_records
from scripts.kyoto_institute_tech_2027_undergrad_extractor import extract_kit_2027_undergrad_records
from scripts.kwansei_2027_undergrad_extractor import extract_kwansei_2027_undergrad_records
from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records
from scripts.osaka_metropolitan_2027_undergrad_extractor import extract_osaka_metropolitan_2027_undergrad_records
from scripts.osaka_university_2026_undergrad_extractor import extract_osaka_university_2026_undergrad_records
from scripts.ritsumeikan_2027_undergrad_extractor import extract_ritsumeikan_2027_undergrad_records
from scripts.tohoku_2026_undergrad_extractor import extract_tohoku_2026_undergrad_records
from scripts.waseda_2027_extractor import extract_waseda_2027_records


Extractor = Callable[[str], list[dict[str, Any]]]


SEED_EXTRACTORS: dict[str, dict[str, Any]] = {
    "meiji_2027_schedule": {
        "stem": "meiji_2027_schedule",
        "id": "meiji-2027-schedule",
        "university": "明治大学",
        "admission_year": "2027",
        "script": "scripts/meiji_schedule_extractor.py",
        "expected_path": "quality_baselines/meiji_2027_schedule.expected.json",
        "source_url": "https://www.meiji.ac.jp/cip/prospective/admission_exams/6t5h7p000001f23y-att/2027intexam.pdf",
        "source_candidates": ["data/uploads/meiji_2027_schedule_official.pdf"],
        "source_markers": ["明治大学", "2027"],
        "text_markers": ["明治大学", "2027年度外国人留学生入学試験", "試験科目・日程等一覧"],
        "extractor": extract_meiji_2027_schedule_records,
    },
    "waseda_2027_official": {
        "stem": "waseda_2027_official",
        "id": "waseda-2027-official",
        "university": "早稲田大学",
        "admission_year": "2027",
        "script": "scripts/waseda_2027_extractor.py",
        "expected_path": "quality_baselines/waseda_2027_official.expected.json",
        "source_url": "https://www.waseda.jp/inst/admission/assets/uploads/2026/02/01_2027_gaikokugakusei_nyushiyoukou.pdf",
        "source_candidates": ["data/uploads/waseda_2027_official.pdf"],
        "source_markers": [["Waseda", "早稲田大学", "早稻田大学"], ["2027", "2027年度"]],
        "text_markers": ["早稲田大学", "2027年度", "外国学生"],
        "extractor": extract_waseda_2027_records,
    },
    "keio_2027_medicine": {
        "stem": "keio_2027_medicine",
        "id": "keio-2027-medicine",
        "university": "慶應義塾大学",
        "admission_year": "2027",
        "script": "scripts/keio_medicine_2027_extractor.py",
        "expected_path": "quality_baselines/keio_2027_medicine.expected.json",
        "source_url": "https://www.keio.ac.jp/files/66f9e69c6550ffb5f9da5ee62c5be61aaba0f159b4e619e4752ebdee5b207fba",
        "source_candidates": ["data/uploads/keio_2027_medicine.pdf"],
        "source_markers": ["慶應義塾大学", "2027年度", "医学部外国人留学生対象"],
        "text_markers": ["慶應義塾大学", "2027年度", "医学部外国人留学生対象", "入学試験募集要項"],
        "extractor": extract_keio_2027_medicine_records,
    },
    "kwansei_2027_undergrad": {
        "stem": "kwansei_2027_undergrad",
        "id": "kwansei-2027-undergrad",
        "university": "関西学院大学",
        "admission_year": "2027",
        "script": "scripts/kwansei_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/kwansei_2027_undergrad.expected.json",
        "source_url": "https://ciec.kwansei.ac.jp/upload/ac1aedfe5e5ec128838c7e4a4cb47ea569d24597.pdf",
        "source_candidates": ["data/uploads/kwansei_2027_undergrad.pdf"],
        "source_markers": ["関西学院大学", "2027年度", "外国人留学生入学試験要項"],
        "text_markers": ["関西学院大学", "2027年度", "外国人留学生入学試験要項"],
        "extractor": extract_kwansei_2027_undergrad_records,
    },
    "kindai_2027_undergrad": {
        "stem": "kindai_2027_undergrad",
        "id": "kindai-2027-undergrad",
        "university": "近畿大学",
        "admission_year": "2027",
        "script": "scripts/kindai_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/kindai_2027_undergrad.expected.json",
        "source_url": "https://www.kindai.ac.jp/files/campus-life/international-exchange/exam/department/entrance-exam-a.pdf",
        "source_candidates": ["data/uploads/kindai_2027_undergrad.pdf"],
        "source_markers": ["2027", "外国人留学生入学試験要項", "近畿大学"],
        "text_markers": ["近畿大学", "2027年度", "外国人留学生入学試験要項"],
        "extractor": extract_kindai_2027_undergrad_records,
    },
    "ritsumeikan_2027_undergrad": {
        "stem": "ritsumeikan_2027_undergrad",
        "id": "ritsumeikan-2027-undergrad",
        "university": "立命館大学",
        "admission_year": "2027",
        "script": "scripts/ritsumeikan_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/ritsumeikan_2027_undergrad.expected.json",
        "source_url": "https://admission.ritsumei.ac.jp/assets/file/2027/admission/international/ryugakusei-youkou.pdf",
        "source_candidates": ["data/uploads/ritsumeikan_2027_undergrad.pdf"],
        "source_markers": ["立命館大学", "2027", "外国人留学生入学試験"],
        "text_markers": ["立命館大学", "2027", "外国人留学生入学試験"],
        "extractor": extract_ritsumeikan_2027_undergrad_records,
    },
    "osaka_metropolitan_2027_undergrad": {
        "stem": "osaka_metropolitan_2027_undergrad",
        "id": "osaka-metropolitan-2027-undergrad",
        "university": "大阪公立大学",
        "admission_year": "2027",
        "script": "scripts/osaka_metropolitan_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/osaka_metropolitan_2027_undergrad.expected.json",
        "source_url": "https://www.omu.ac.jp/admissions/assets/2027_international_student_pre_guide.pdf",
        "source_candidates": ["data/uploads/osaka_metropolitan_2027_undergrad.pdf"],
        "source_markers": ["2027", "⚾㈝እᅜே␃Ꮫ"],
        "text_markers": ["2027", "␃Ꮫ", "ヨ㦂"],
        "extractor": extract_osaka_metropolitan_2027_undergrad_records,
    },
    "chukyo_gakuin_2027_undergrad": {
        "stem": "chukyo_gakuin_2027_undergrad",
        "id": "chukyo-gakuin-2027-undergrad",
        "university": "中京学院大学",
        "admission_year": "2027",
        "script": "scripts/chukyo_gakuin_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/chukyo_gakuin_2027_undergrad.expected.json",
        "source_url": "https://secondhome.chukyogakuin-u.ac.jp/media/youkou-foreign-2027.pdf",
        "source_candidates": ["data/uploads/chukyo_gakuin_2027_undergrad.pdf"],
        "source_markers": ["2027", "中京学院大学", "外国人留学生選抜"],
        "text_markers": ["中京学院大学", "2027", "外国人留学生選抜"],
        "extractor": extract_chukyo_gakuin_2027_undergrad_records,
    },
    "kyoto_institute_tech_2027_undergrad": {
        "stem": "kyoto_institute_tech_2027_undergrad",
        "id": "kit-2027-undergrad",
        "university": "京都工芸繊維大学",
        "admission_year": "2027",
        "script": "scripts/kyoto_institute_tech_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/kyoto_institute_tech_2027_undergrad.expected.json",
        "source_url": "https://ac.web.kit.ac.jp/02/nyushi/yoko/gakubu/2027_shihi_yoko.pdf",
        "source_candidates": ["data/uploads/kyoto_institute_tech_2027_undergrad.pdf"],
        "source_markers": ["2027年度", "京都工芸繊維大学", "私費外国人留学生入試"],
        "text_markers": ["京都工芸繊維大学", "2027", "私費外国人留学生入試"],
        "extractor": extract_kit_2027_undergrad_records,
    },
    "fukui_engineering_2027_undergrad": {
        "stem": "fukui_engineering_2027_undergrad",
        "id": "fukui-engineering-2027-undergrad",
        "university": "福井大学",
        "admission_year": "2027",
        "script": "scripts/fukui_engineering_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/fukui_engineering_2027_undergrad.expected.json",
        "source_url": "https://www.u-fukui.ac.jp/wp/wp-content/uploads/bsy27_shihiryu_youkou.pdf",
        "source_candidates": ["data/uploads/fukui_engineering_2027_undergrad.pdf"],
        "source_markers": ["2027", "福井大学", "工学部", "私費外国人留学生選抜"],
        "text_markers": ["福井大学", "工学部", "私費外国人留学生選抜"],
        "extractor": extract_fukui_engineering_2027_undergrad_records,
    },
    "hokkaido_2027_undergrad": {
        "stem": "hokkaido_2027_undergrad",
        "id": "hokkaido-2027-undergrad",
        "university": "北海道大学",
        "admission_year": "2027",
        "script": "scripts/hokkaido_2027_undergrad_extractor.py",
        "expected_path": "quality_baselines/hokkaido_2027_undergrad.expected.json",
        "source_url": "https://www.hokudai.ac.jp/admission/R9_shihi_kihonhoushin.pdf",
        "source_candidates": ["data/uploads/hokkaido_2027_undergrad.pdf"],
        "source_markers": ["私費外国人留学生", "令和９(2027)年度", "日本留学試験", "出願期間"],
        "text_markers": ["令和9(2027)年度", "私費外国人留学生", "入試基本方針", "日本留学試験"],
        "extractor": extract_hokkaido_2027_undergrad_records,
    },
    "tohoku_2026_undergrad": {
        "stem": "tohoku_2026_undergrad",
        "id": "tohoku-2026-undergrad",
        "university": "東北大学",
        "admission_year": "2026",
        "script": "scripts/tohoku_2026_undergrad_extractor.py",
        "expected_path": "quality_baselines/tohoku_2026_undergrad.expected.json",
        "source_url": "https://admissions.tohoku.ac.jp/ja/adcms/wp-content/uploads/2025/12/r8shihi.pdf",
        "source_candidates": ["data/uploads/tohoku_2026_undergrad.pdf"],
        "source_markers": ["東北大学", "私費外国人留学生", "日本留学試験", "出 願 受 付 期 間"],
        "text_markers": ["令和8年度", "東北大学", "私費外国人留学生入試", "日本留学試験"],
        "extractor": extract_tohoku_2026_undergrad_records,
    },
    "osaka_university_2026_undergrad": {
        "stem": "osaka_university_2026_undergrad",
        "id": "osaka-university-2026-undergrad",
        "university": "大阪大学",
        "admission_year": "2026",
        "script": "scripts/osaka_university_2026_undergrad_extractor.py",
        "expected_path": "quality_baselines/osaka_university_2026_undergrad.expected.json",
        "source_url": "https://www.osaka-u.ac.jp/ja/admissions/faculty/expense/files/2026shihi_guideline-1.pdf/@@download/file",
        "source_candidates": ["data/uploads/osaka_university_2026_undergrad.pdf"],
        "source_markers": ["大阪大学", "私費外国人留学生特別入試", "日本留学試験", "TOEFL"],
        "text_markers": ["大阪大学", "私費外国人留学生特別入試", "日本留学試験", "TOEFL"],
        "extractor": extract_osaka_university_2026_undergrad_records,
    },
}


def registered_seed_extractors() -> dict[str, dict[str, Any]]:
    return dict(SEED_EXTRACTORS)


def _has_all_markers(text: str, markers: list[Any]) -> bool:
    for marker in markers:
        if isinstance(marker, list):
            if not any(str(item) in text for item in marker if str(item).strip()):
                return False
        elif str(marker) not in text:
            return False
    return True


def seed_for_source(university: str, year: str, text: str) -> dict[str, Any] | None:
    for seed in SEED_EXTRACTORS.values():
        if str(seed.get("university")) != str(university):
            continue
        if str(seed.get("admission_year")) != str(year):
            continue
        if _has_all_markers(text, list(seed.get("text_markers") or [])):
            return seed
    return None
