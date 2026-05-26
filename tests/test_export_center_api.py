from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient
from openpyxl import load_workbook


class ExportCenterApiTest(unittest.TestCase):
    def _load_api(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "export_center_test.db")
        os.environ["OWNER_EMAIL"] = "owner@example.com"
        os.environ["OWNER_PASSWORD"] = "owner-admin"
        for name in ("DATABASE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
            os.environ.pop(name, None)
        for module_name in ["scripts.api", "scripts.db"]:
            sys.modules.pop(module_name, None)
        api = importlib.import_module("scripts.api")
        db = importlib.import_module("scripts.db")
        return api, db

    def _login_owner(self, client: TestClient) -> None:
        response = client.post("/auth/login", json={"email": "owner@example.com", "password": "owner-admin"})
        self.assertEqual(response.status_code, 200)

    def _insert_confirmed(self, db, university: str, year: str, faculty: str) -> int:
        doc_id = db.create_source_document(
            university,
            f"{university}.pdf",
            f"/tmp/{university}.pdf",
            f"https://example.test/{university}.pdf",
            year,
        )
        conn = db.get_conn()
        conn.execute(
            """
            INSERT INTO admission_records (
                source_staging_id, document_id, university, pdf_url, admission_year,
                admission_period, faculty, department, application_period, deadline_rule,
                eju_session, eju_japanese, eju_general, eju_math, eju_physics,
                eju_chemistry, eju_biology, english_requirement, screening_method,
                screening_schedule, result_date, enrollment_period, prefecture, campus,
                eligibility, required_documents, evidence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                None,
                doc_id,
                university,
                f"https://example.test/{university}.pdf",
                year,
                "April",
                faculty,
                "Department",
                "2026-01-10 - 2026-01-20",
                "Must arrive by deadline",
                "2025 June or November",
                "Japanese required",
                "General subject",
                "Math course 2",
                "Physics",
                "Chemistry",
                "",
                "TOEFL iBT",
                "Documents and interview",
                "2026-02-25",
                "2026-03-07",
                "2026-03-18",
                "Tokyo",
                "Main",
                "Completed 12 years of school education outside Japan",
                "Graduation certificate / Transcript / Statement of purpose",
                "Guideline p.3-p.7",
            ),
        )
        conn.commit()
        conn.close()
        return doc_id

    def _insert_confirmed_with_gaps(self, db, university: str, year: str, faculty: str) -> int:
        doc_id = db.create_source_document(
            university,
            f"{university}.pdf",
            f"/tmp/{university}.pdf",
            f"https://example.test/{university}.pdf",
            year,
        )
        conn = db.get_conn()
        conn.execute(
            """
            INSERT INTO admission_records (
                source_staging_id, document_id, university, pdf_url, admission_year,
                admission_period, faculty, department, application_period, deadline_rule,
                eju_session, eju_japanese, eju_general, eju_math, eju_physics,
                eju_chemistry, eju_biology, english_requirement, screening_method,
                screening_schedule, result_date, enrollment_period, prefecture, campus,
                eligibility, required_documents, evidence
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                None,
                doc_id,
                university,
                f"https://example.test/{university}.pdf",
                year,
                "April",
                faculty,
                "Department",
                "",
                "Must arrive by deadline",
                "2025 June or November",
                "",
                "General subject",
                "Math course 2",
                "Physics",
                "Chemistry",
                "",
                "",
                "Documents and interview",
                "",
                "",
                "2026-03-18",
                "Tokyo",
                "Main",
                "",
                "",
                "",
            ),
        )
        conn.commit()
        conn.close()
        return doc_id

    def test_export_preview_filters_confirmed_rows_and_hides_quality_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Waseda University", "2027", "Law")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/exports/preview", params={"universities": "Meiji,Waseda", "years": "2027"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["records"], 2)
        self.assertEqual(payload["summary"]["universities"], 2)
        self.assertTrue(payload["summary"]["ready_for_export"])
        self.assertEqual(payload["summary"]["missing_required"]["application_period"], 0)
        self.assertEqual(payload["rows"][0]["export_missing"], [])
        self.assertEqual(
            {(target["university"], target["admission_year"]) for target in payload["review_targets"]},
            {("Meiji University", "2027"), ("Waseda University", "2027")},
        )
        self.assertTrue(all(target["doc_id"] for target in payload["review_targets"]))
        self.assertEqual({row["university"] for row in payload["rows"]}, {"Meiji University", "Waseda University"})
        for hidden_key in ("confidence", "risk_level", "field_evidence", "raw_llm_json", "warnings_json"):
            self.assertNotIn(hidden_key, payload["rows"][0])

    def test_export_preview_reports_missing_required_content_without_internal_quality_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Ready University", "2027", "Science")
            self._insert_confirmed_with_gaps(db, "Gap University", "2027", "Letters")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/exports/preview", params={"years": "2027"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["records"], 2)
        self.assertFalse(payload["summary"]["ready_for_export"])
        self.assertEqual(payload["summary"]["missing_required"]["application_period"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["eju_japanese"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["english_requirement"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["screening_schedule"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["result_date"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["eligibility"], 1)
        self.assertEqual(payload["summary"]["missing_required"]["required_documents"], 1)
        self.assertEqual(len(payload["review_targets"]), 2)
        gap_row = next(row for row in payload["rows"] if row["university"] == "Gap University")
        self.assertTrue(gap_row["review_doc_id"])
        self.assertNotIn("document_id", gap_row)
        self.assertEqual(
            set(gap_row["export_missing"]),
            {"application_period", "eju_japanese", "english_requirement", "screening_schedule", "result_date", "eligibility", "required_documents"},
        )
        for hidden_key in ("confidence", "risk_level", "field_evidence", "raw_llm_json", "warnings_json"):
            self.assertNotIn(hidden_key, str(payload))

    def test_export_preview_keeps_precise_review_target_without_leaking_staging_column(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            doc_id = db.create_source_document(
                "Same Faculty University",
                "same.pdf",
                "/tmp/same.pdf",
                "https://example.test/same.pdf",
                "2027",
            )
            first_staging_id = db.insert_staging_record(
                doc_id,
                1,
                {
                    "university": "Same Faculty University",
                    "admission_year": "2027",
                    "faculty": "Letters",
                    "department": "First Department",
                    "application_period": "",
                    "needs_review": 1,
                },
            )
            second_staging_id = db.insert_staging_record(
                doc_id,
                2,
                {
                    "university": "Same Faculty University",
                    "admission_year": "2027",
                    "faculty": "Letters",
                    "department": "Second Department",
                    "application_period": "2026-09-01 - 2026-09-10",
                    "needs_review": 0,
                },
            )
            conn = db.get_conn()
            for staging_id, department, application_period in (
                (first_staging_id, "First Department", ""),
                (second_staging_id, "Second Department", "2026-09-01 - 2026-09-10"),
            ):
                conn.execute(
                    """
                    INSERT INTO admission_records (
                        source_staging_id, document_id, university, pdf_url, admission_year,
                        admission_period, faculty, department, application_period, deadline_rule,
                        eju_session, eju_japanese, eju_general, eju_math, eju_physics,
                        eju_chemistry, eju_biology, english_requirement, screening_method,
                        screening_schedule, result_date, enrollment_period, prefecture, campus,
                        eligibility, required_documents, evidence
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        staging_id,
                        doc_id,
                        "Same Faculty University",
                        "https://example.test/same.pdf",
                        "2027",
                        "April",
                        "Letters",
                        department,
                        application_period,
                        "Must arrive by deadline",
                        "2025 June or November",
                        "Japanese required",
                        "General subject",
                        "Math course 1",
                        "",
                        "",
                        "",
                        "TOEFL iBT",
                        "Documents",
                        "2026-02-25",
                        "2026-03-07",
                        "2026-03-18",
                        "Tokyo",
                        "Main",
                        "Completed 12 years of school education outside Japan",
                        "Graduation certificate / Transcript",
                        "Guideline p.3-p.7",
                    ),
                )
            conn.commit()
            conn.close()
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/exports/preview", params={"universities": "Same Faculty University", "years": "2027"})
            issue_response = client.get("/metrics/owner-issues")

        self.assertEqual(response.status_code, 200)
        rows = response.json()["rows"]
        by_department = {row["department"]: row for row in rows}
        self.assertEqual(by_department["First Department"]["review_staging_id"], first_staging_id)
        self.assertEqual(by_department["Second Department"]["review_staging_id"], second_staging_id)
        self.assertEqual(by_department["First Department"]["review_doc_id"], doc_id)
        self.assertNotIn("source_staging_id", by_department["First Department"])
        self.assertNotIn("document_id", by_department["First Department"])
        self.assertEqual(issue_response.status_code, 200)
        gap_issue = next(
            item
            for item in issue_response.json()["issues"]
            if item["kind"] == "export_gap" and item["department"] == "First Department"
        )
        self.assertEqual(gap_issue["review_staging_id"], first_staging_id)

    def test_owner_issues_requires_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            client = TestClient(api.app)

            response = client.get("/metrics/owner-issues")

        self.assertEqual(response.status_code, 401)

    def test_owner_issues_points_export_gaps_to_review_source(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed_with_gaps(db, "Gap University", "2027", "Letters")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["summary"]["export_ready"])
        self.assertGreaterEqual(payload["summary"]["by_kind"]["export_gap"], 1)
        issue = next(item for item in payload["issues"] if item["kind"] == "export_gap")
        self.assertEqual(issue["university"], "Gap University")
        self.assertEqual(issue["admission_year"], "2027")
        self.assertIn(issue["field"], {"application_period", "eju_japanese", "english_requirement", "screening_schedule", "result_date", "eligibility", "required_documents"})
        self.assertEqual(issue["source_document"], "Gap University.pdf")
        self.assertTrue(issue["doc_id"])
        self.assertIn("review_staging_id", issue)
        self.assertIn("复审页", issue["suggested_action"])

    def test_owner_issues_summary_counts_full_backlog_before_display_limit(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed_with_gaps(db, "First Gap University", "2027", "Letters")
            self._insert_confirmed_with_gaps(db, "Second Gap University", "2027", "Science")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues", params={"limit": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(len(payload["issues"]), 1)
        self.assertEqual(payload["summary"]["shown"], 1)
        self.assertGreater(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["by_kind"]["export_gap"], payload["summary"]["total"])
        self.assertEqual(payload["summary"]["export_records"], 2)
        self.assertTrue(payload["summary"]["has_export_records"])

    def test_owner_issues_distinguishes_empty_export_library_from_export_gaps(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total"], 0)
        self.assertEqual(payload["summary"]["export_records"], 0)
        self.assertFalse(payload["summary"]["has_export_records"])
        self.assertFalse(payload["summary"]["export_ready"])

    def test_owner_issues_use_exact_document_for_same_school_year_export_gap(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            ready_doc_id = self._insert_confirmed(db, "Same University", "2027", "Ready Faculty")
            gap_doc_id = self._insert_confirmed_with_gaps(db, "Same University", "2027", "Gap Faculty")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        gap_issue = next(
            item
            for item in payload["issues"]
            if item["kind"] == "export_gap" and item["university"] == "Same University"
        )
        self.assertEqual(gap_issue["doc_id"], gap_doc_id)
        self.assertNotEqual(gap_issue["doc_id"], ready_doc_id)
        self.assertIsNone(gap_issue["review_staging_id"])
        self.assertEqual(gap_issue["source_document"], "Same University.pdf")

    def test_owner_issues_can_be_downloaded_as_csv(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed_with_gaps(db, "Gap University", "2027", "Letters")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues.csv")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("owner-quality-issues.csv", response.headers.get("content-disposition", ""))
        self.assertIn("Gap University", response.text)
        self.assertIn("suggested_action", response.text)

    def test_owner_issues_adds_source_context_to_baseline_gaps(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            original_overview = api.build_quality_overview

            def fake_overview(*, include_source_text_health: bool = False):
                return {
                    "overall_status": "needs_owner_action",
                    "per_seed_thin_coverage": [
                        {"seed": "waseda-2027-official", "field": "eju_japanese", "checked": 1, "minimum": 3}
                    ],
                    "quality_todo": [
                        {
                            "priority": 40,
                            "action": "critical_field_coverage_below_target",
                            "field": "eju_japanese",
                            "checked": 1,
                            "minimum": 5,
                            "details": "Add checked EJU Japanese rows.",
                        }
                    ],
                }

            api.build_quality_overview = fake_overview
            client = TestClient(api.app)
            self._login_owner(client)

            try:
                response = client.get("/metrics/owner-issues")
                csv_response = client.get("/metrics/owner-issues.csv")
            finally:
                api.build_quality_overview = original_overview

        self.assertEqual(response.status_code, 200)
        issue = next(item for item in response.json()["issues"] if item["kind"] == "baseline_gap")
        self.assertEqual(issue["seed_id"], "waseda-2027-official")
        self.assertEqual(issue["admission_year"], "2027")
        self.assertEqual(issue["source_document"], "data/uploads/waseda_2027_official.pdf")
        self.assertIn("waseda.jp", issue["source_url"])
        self.assertIn("scripts/waseda_2027_extractor.py", issue["script"])
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("seed_id", csv_response.text)
        self.assertIn("waseda-2027-official", csv_response.text)

    def test_owner_issues_manual_corrections_link_back_to_review_document(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            doc_id = db.create_source_document(
                "Review University",
                "review.pdf",
                "/tmp/review.pdf",
                "https://example.test/review.pdf",
                "2027",
            )
            staging_id = db.insert_staging_record(
                doc_id,
                4,
                {
                    "university": "Review University",
                    "admission_year": "2027",
                    "faculty": "Policy",
                    "department": "Policy",
                    "application_period": "",
                    "english_requirement": "",
                    "screening_method": "Documents",
                    "needs_review": True,
                },
            )
            db.update_staging_record(
                staging_id,
                {
                    "application_period": "2026-09-01 - 2026-09-10",
                    "is_reviewed": 1,
                },
            )
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/metrics/owner-issues")
            csv_response = client.get("/metrics/owner-issues.csv")

        self.assertEqual(response.status_code, 200)
        issue = next(item for item in response.json()["issues"] if item["kind"] == "manual_correction")
        self.assertEqual(issue["doc_id"], doc_id)
        self.assertEqual(issue["document_id"], doc_id)
        self.assertEqual(issue["field"], "application_period")
        self.assertEqual(issue["source_document"], "review.pdf")
        self.assertEqual(csv_response.status_code, 200)
        self.assertIn("doc_id", csv_response.text.splitlines()[0])
        self.assertIn("review_staging_id", csv_response.text.splitlines()[0])
        self.assertIn(str(doc_id), csv_response.text)

    def test_export_csv_uses_same_filters(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/export/csv", params={"universities": "Kyushu", "years": "2026"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.headers["content-type"])
        self.assertTrue(response.content.startswith(b"\xef\xbb\xbf"))
        self.assertIn("admissions_Kyushu_University_2026_Engineering.csv", response.headers["content-disposition"])
        body = response.text
        header = body.splitlines()[0]
        self.assertIn("学校", header)
        self.assertIn("英语要求", header)
        self.assertIn("来源依据", header)
        for internal_key in ("id", "document_id", "source_staging_id", "pdf_url", "export_missing"):
            self.assertNotIn(internal_key, header)
        self.assertIn("Kyushu University", body)
        self.assertNotIn("Meiji University", body)

    def test_export_csv_supports_single_school_filters(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/export/csv", params={"university": "Meiji", "year": 2027, "faculty": "Science"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("admissions_Meiji_University_2027_Science.csv", response.headers["content-disposition"])
        self.assertIn("Meiji University", response.text)
        self.assertNotIn("Kyushu University", response.text)

    def test_export_filters_accept_common_spreadsheet_separators(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            self._insert_confirmed(db, "Waseda University", "2027", "Commerce")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get(
                "/exports/preview",
                params={
                    "universities": "Meiji University，Kyushu University、Missing University",
                    "years": "2027；2026",
                    "faculties": "Science;Engineering",
                },
            )

        self.assertEqual(response.status_code, 200)
        rows = response.json()["rows"]
        self.assertEqual({row["university"] for row in rows}, {"Meiji University", "Kyushu University"})
        self.assertEqual(response.json()["summary"]["records"], 2)

    def test_export_preview_and_excel_can_use_selected_record_ids(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Waseda University", "2027", "Law")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            client = TestClient(api.app)
            self._login_owner(client)

            all_rows = client.get("/exports/preview").json()["rows"]
            selected_ids = ",".join(str(row["id"]) for row in all_rows if row["university"] in {"Meiji University", "Kyushu University"})
            preview = client.get("/exports/preview", params={"record_ids": selected_ids})
            excel = client.get("/export/excel", params={"record_ids": selected_ids})

        self.assertEqual(preview.status_code, 200)
        payload = preview.json()
        self.assertEqual(payload["summary"]["records"], 2)
        self.assertEqual({row["university"] for row in payload["rows"]}, {"Meiji University", "Kyushu University"})
        self.assertEqual(excel.status_code, 200)
        self.assertIn("admissions_selected_2rows.xlsx", excel.headers["content-disposition"])
        wb = load_workbook(BytesIO(excel.content))
        self.assertEqual(wb.sheetnames[:3], ["导出说明", "学校汇总", "招生资料"])
        summary = wb["导出说明"]
        self.assertEqual(summary["A4"].value, "资料条数")
        self.assertEqual(summary["B4"].value, 2)
        school_summary = wb["学校汇总"]
        self.assertEqual([cell.value for cell in school_summary[1]], ["学校", "年度", "学部数量", "资料条数"])
        self.assertEqual(
            {(school_summary.cell(row=row_number, column=1).value, school_summary.cell(row=row_number, column=4).value) for row_number in range(2, school_summary.max_row + 1)},
            {("Meiji University", 1), ("Kyushu University", 1)},
        )
        ws = wb["招生资料"]
        exported_universities = {ws.cell(row=row_number, column=1).value for row_number in range(4, ws.max_row + 1)}
        self.assertEqual(exported_universities, {"Meiji University", "Kyushu University"})

    def test_export_options_list_confirmed_values_for_owner(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            self._insert_confirmed(db, "Meiji University", "2027", "Law")
            self._insert_confirmed(db, "Kyushu University", "2026", "Engineering")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/exports/options")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["universities"][0]["value"], "Meiji University")
        self.assertEqual(payload["universities"][0]["count"], 2)
        self.assertIn({"value": "2027", "count": 2}, payload["years"])
        self.assertIn({"value": "Science", "count": 1}, payload["faculties"])
        for hidden_key in ("confidence", "risk_level", "field_evidence", "raw_llm_json", "warnings_json"):
            self.assertNotIn(hidden_key, str(payload))

    def test_document_list_includes_review_count_for_owner_queue_status(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            doc_id = db.create_source_document(
                "Review Queue University",
                "review-queue.pdf",
                "/tmp/review-queue.pdf",
                "https://example.test/review-queue.pdf",
                "2027",
            )
            db.insert_staging_record(
                doc_id,
                1,
                {
                    "university": "Review Queue University",
                    "admission_year": "2027",
                    "faculty": "Letters",
                    "department": "Department",
                    "needs_review": 1,
                },
            )
            db.insert_staging_record(
                doc_id,
                2,
                {
                    "university": "Review Queue University",
                    "admission_year": "2027",
                    "faculty": "Law",
                    "department": "Department",
                    "needs_review": 0,
                    "is_reviewed": 1,
                },
            )
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/documents", params={"q": "Review Queue"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload[0]["staging_count"], 2)
        self.assertEqual(payload[0]["review_count"], 1)
        self.assertEqual(payload[0]["confirmed_count"], 0)

    def test_export_excel_hides_internal_quality_columns(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed(db, "Meiji University", "2027", "Science")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get("/export/excel", params={"universities": "Meiji", "years": "2027"})

        self.assertEqual(response.status_code, 200)
        self.assertIn("admissions_Meiji_University_2027_Science.xlsx", response.headers["content-disposition"])
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(wb.sheetnames, ["导出说明", "学校汇总", "招生资料"])
        summary = wb["导出说明"]
        self.assertEqual(summary["B4"].value, 1)
        self.assertEqual(summary["B5"].value, 1)
        self.assertIn("2027", summary["B6"].value)
        self.assertIn("Science", summary["B7"].value)
        self.assertNotIn("risk", str(summary.values))
        school_summary = wb["学校汇总"]
        self.assertEqual(school_summary["A2"].value, "Meiji University")
        self.assertEqual(school_summary["B2"].value, "2027")
        self.assertEqual(school_summary["C2"].value, 1)
        self.assertEqual(school_summary["D2"].value, 1)
        ws = wb["招生资料"]
        headers = [ws.cell(row=3, column=index + 1).value for index in range(ws.max_column)]
        self.assertIn("学校", headers)
        self.assertIn("英语要求", headers)
        self.assertIn("出愿资格", headers)
        self.assertIn("所需材料", headers)
        self.assertIn("来源依据", headers)
        for hidden_label in ("置信度", "是否需要复核", "风险等级", "警告/备注", "信頼度", "要確認", "リスク"):
            self.assertNotIn(hidden_label, headers)
        self.assertEqual(ws.cell(row=4, column=1).value, "Meiji University")

    def test_export_routes_require_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            client = TestClient(api.app)

            preview = client.get("/exports/preview")
            options = client.get("/exports/options")
            csv_response = client.get("/export/csv")

        self.assertEqual(preview.status_code, 401)
        self.assertEqual(options.status_code, 401)
        self.assertEqual(csv_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
