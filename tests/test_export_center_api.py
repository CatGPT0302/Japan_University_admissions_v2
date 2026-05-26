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

    def _insert_confirmed(self, db, university: str, year: str, faculty: str) -> None:
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
                screening_schedule, result_date, enrollment_period, prefecture, campus
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            ),
        )
        conn.commit()
        conn.close()

    def _insert_confirmed_with_gaps(self, db, university: str, year: str, faculty: str) -> None:
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
                screening_schedule, result_date, enrollment_period, prefecture, campus
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
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
            ),
        )
        conn.commit()
        conn.close()

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
        self.assertEqual(len(payload["review_targets"]), 2)
        gap_row = next(row for row in payload["rows"] if row["university"] == "Gap University")
        self.assertEqual(
            set(gap_row["export_missing"]),
            {"application_period", "eju_japanese", "english_requirement", "screening_schedule", "result_date"},
        )
        for hidden_key in ("confidence", "risk_level", "field_evidence", "raw_llm_json", "warnings_json"):
            self.assertNotIn(hidden_key, str(payload))

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
        self.assertIn(issue["field"], {"application_period", "eju_japanese", "english_requirement", "screening_schedule", "result_date"})
        self.assertEqual(issue["source_document"], "Gap University.pdf")
        self.assertTrue(issue["doc_id"])
        self.assertIn("复审页", issue["suggested_action"])

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
        body = response.text
        self.assertIn("Kyushu University", body)
        self.assertNotIn("Meiji University", body)

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
        wb = load_workbook(BytesIO(excel.content))
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
        wb = load_workbook(BytesIO(response.content))
        self.assertEqual(wb.sheetnames, ["招生资料"])
        ws = wb["招生资料"]
        headers = [ws.cell(row=3, column=index + 1).value for index in range(ws.max_column)]
        self.assertIn("学校", headers)
        self.assertIn("英语要求", headers)
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
