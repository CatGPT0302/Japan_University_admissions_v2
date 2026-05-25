from __future__ import annotations

from typing import Any, Callable

from scripts.meiji_schedule_extractor import extract_meiji_2027_schedule_records
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
        "source_candidates": ["data/uploads/waseda_2027_official.pdf"],
        "source_markers": [["Waseda", "早稲田大学", "早稻田大学"], ["2027", "2027年度"]],
        "text_markers": ["早稲田大学", "2027年度", "外国学生"],
        "extractor": extract_waseda_2027_records,
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
