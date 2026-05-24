from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


WASEDA_TEXT = """
早稲田大学 2027年度外国学生のための学部入学試験要項
出願期間 2026年6月1日(月) 10:00 ～ 6月18日(木) 17:00
(3)入学試験日程・選考方法
法学部 書類選考 面接試験 9月18日 10月1日 TOEFL IELTS
商学部 書類選考 面接試験 オンライン 10月3日 10月15日 TOEFL
社会科学部 書類選考 面接試験 オンライン 9月18日 10月9日 TOEFL
基幹理工学部 学系1 書類選考 面接試験 9月28日 10月26日 TOEFL IELTS TOEIC
スポーツ科学部 書類選考 面接試験 オンライン 9月11日 9月18日 TOEFL
"""


class Waseda2027ExtractorTest(unittest.TestCase):
    def test_extracts_seed_records_that_pass_waseda_baseline(self) -> None:
        from scripts.quality_baseline import evaluate_against_expected, load_json_records
        from scripts.waseda_2027_extractor import extract_waseda_2027_records

        records = extract_waseda_2027_records(WASEDA_TEXT)
        expected = load_json_records(ROOT / "quality_baselines" / "waseda_2027_official.expected.json")
        report = evaluate_against_expected(expected, records)

        self.assertEqual(len(records), 5)
        self.assertTrue(report["passed"], report)

    def test_returns_no_records_for_unrelated_text(self) -> None:
        from scripts.waseda_2027_extractor import extract_waseda_2027_records

        self.assertEqual(extract_waseda_2027_records("明治大学 2027年度 入試日程"), [])

    def test_cli_reads_text_file_and_writes_records_json(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "waseda.txt"
            output_path = tmp_path / "records.json"
            input_path.write_text(WASEDA_TEXT, encoding="utf-8")

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "waseda_2027_extractor.py"),
                    "--text",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            payload = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["record_count"], 5)
            self.assertEqual(payload["records"][0]["university"], "早稲田大学")

    def test_text_path_uses_waseda_seed_without_llm_call(self) -> None:
        from scripts.extract_direct import _run_text_path

        with (
            patch("scripts.extract_direct._read_pdf_text", return_value=(WASEDA_TEXT, {1: WASEDA_TEXT})),
            patch("scripts.extract_direct._insert_result", return_value=5) as insert_result,
            patch("scripts.extract_direct._call_openai", side_effect=AssertionError("LLM should not be called")),
        ):
            result = _run_text_path(1, Path("dummy.pdf"), "早稲田大学", "2027")

        self.assertEqual(result["mode"], "deterministic_text")
        self.assertEqual(result["records"], 5)
        self.assertEqual(result["inserted"], 5)
        insert_result.assert_called_once()


if __name__ == "__main__":
    unittest.main()
