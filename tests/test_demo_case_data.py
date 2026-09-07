"""Regression checks for the directly read sample data, not accuracy certification."""
import json
from pathlib import Path


def test_kit_course_specific_selection_and_erratum_are_retained():
    package = json.loads((Path(__file__).resolve().parents[1] / "examples/demo/kit_2027_codex.json").read_text())
    records = {row["department"]: row for row in package["records"]}
    assert len(records) == 7
    assert "から2科目" in records["応用生物学課程"]["eju_biology"]
    assert "必須" in records["応用化学課程"]["eju_physics"]
    assert "課さない" in records["応用化学課程"]["eju_biology"]
    for course in ("電子システム工学課程", "情報工学課程", "機械工学課程"):
        assert "必須" in records[course]["eju_physics"]
        assert "化学・生物から1科目" in records[course]["eju_chemistry"]
    for course in ("建築コース", "デザインコース"):
        assert "から1科目" in records[f"デザイン・建築学課程 {course}"]["eju_biology"]
    for row in records.values():
        assert "280/400" in row["eju_japanese"]
        assert "120/200" in row["eju_math"]
        assert "大学入学に支障のない在留資格" in row["eligibility"]
        assert row["field_evidence"]["eligibility"]["page"] == 3
        assert "2026-07-17" in row["deadline_rule"]
        assert "予定" in row["result_date"]
