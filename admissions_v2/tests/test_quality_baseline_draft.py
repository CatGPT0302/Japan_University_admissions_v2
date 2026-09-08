from __future__ import annotations

import unittest
import json
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory


ROOT = Path(__file__).resolve().parents[1]


class QualityBaselineDraftTest(unittest.TestCase):
    def test_builds_reviewable_expected_records_from_extracted_records(self) -> None:
        from scripts.make_quality_baseline_draft import build_baseline_draft

        draft = build_baseline_draft(
            [
                {
                    "university": "明治大学",
                    "admission_year": "2027",
                    "faculty": "法学部",
                    "department": "法律学科",
                    "application_period": "2026年9月15日 to 9月18日",
                    "deadline": "締切日必着",
                    "eju_session": "2025年度第2回 or 2026年度第1回",
                    "eju_subjects": "日本語、総合科目、数学",
                    "english_requirement": "TOEFL iBT 49以上",
                    "screening_method": "書類選考、小論文、口頭試問",
                    "screening_schedule": "2026年11月9日",
                    "result_date": "2026年11月21日",
                }
            ],
            max_records=10,
        )

        self.assertEqual(len(draft), 1)
        self.assertEqual(draft[0]["id"], "meiji-2027-001")
        self.assertEqual(
            draft[0]["match"],
            {
                "university": "明治大学",
                "admission_year": "2027",
                "faculty": "法学部",
                "department": "法律学科",
            },
        )
        self.assertEqual(draft[0]["expect"]["deadline_rule"], "締切日必着")
        self.assertEqual(draft[0]["expect"]["eju_subjects"]["contains"], ["日本語", "総合科目", "数学"])
        self.assertEqual(draft[0]["review_status"], "draft_needs_human_check")

    def test_skips_records_without_identity(self) -> None:
        from scripts.make_quality_baseline_draft import build_baseline_draft

        draft = build_baseline_draft(
            [
                {"university": "明治大学", "faculty": "", "department": "法律学科"},
                {"university": "明治大学", "faculty": "法学部", "department": ""},
            ]
        )

        self.assertEqual(draft, [])

    def test_script_can_run_directly(self) -> None:
        with TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            output_path = tmp_path / "draft.json"
            input_path.write_text(
                json.dumps(
                    {
                        "records": [
                            {
                                "university": "明治大学",
                                "admission_year": "2027",
                                "faculty": "法学部",
                                "department": "法律学科",
                                "application_period": "June",
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "make_quality_baseline_draft.py"),
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
                cwd=ROOT,
                check=True,
            )

            draft = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(draft[0]["id"], "meiji-2027-001")


if __name__ == "__main__":
    unittest.main()
