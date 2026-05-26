from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient


class PublicUserApiTest(unittest.TestCase):
    def _load_api(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "public_api_test.db")
        os.environ["OWNER_EMAIL"] = "owner@example.com"
        os.environ["OWNER_PASSWORD"] = "owner-admin"
        os.environ["PARTNER_EMAIL"] = "partner@example.com"
        os.environ["PARTNER_PASSWORD"] = "partner-demo"
        os.environ.pop("ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW", None)
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
        self.assertEqual(response.json()["user"]["role"], "owner_admin")

    def _login_partner(self, client: TestClient) -> None:
        response = client.post("/auth/login", json={"email": "partner@example.com", "password": "partner-demo"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user"]["role"], "partner_staff")

    def test_upload_uses_unique_saved_names_for_same_basename(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            first = client.post("/upload", files={"file": ("meiji.pdf", b"%PDF-1.4 first", "application/pdf")})
            second = client.post("/upload", files={"file": ("meiji.pdf", b"%PDF-1.4 second", "application/pdf")})

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertNotEqual(first.json()["file_name"], second.json()["file_name"])
        self.assertEqual(first.json()["original_file_name"], "meiji.pdf")
        self.assertEqual(second.json()["original_file_name"], "meiji.pdf")

    def _insert_confirmed_program(self, db: Any, *, university: str = "明治大学", faculty: str = "理工学部") -> int:
        doc_id = db.create_source_document(
            university,
            "meiji.pdf",
            "/tmp/meiji.pdf",
            "https://example.ac.jp/meiji.pdf",
            "2027",
        )
        conn = db.get_conn()
        cur = conn.execute(
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
                "https://example.ac.jp/meiji.pdf",
                "2027",
                "前期",
                faculty,
                "機械工学科",
                "2026年8月25日 - 2026年9月1日",
                "締切日必着",
                "2025年度第1回 / 第2回",
                "日本語",
                "",
                "数学コース2",
                "物理",
                "化学",
                "",
                "TOEFL iBT 48以上",
                "書類選考; 口頭試問",
                "2026年11月28日",
                "2026年12月3日",
                "",
                "東京都",
                "中野キャンパス",
            ),
        )
        program_id = int(cur.lastrowid)
        conn.commit()
        conn.close()
        db.insert_staging_record(
            doc_id,
            None,
            {
                "university": university,
                "admission_year": "2027",
                "faculty": "未確認学部",
                "department": "未確認学科",
                "risk_level": "high",
                "needs_review": True,
            },
        )
        return program_id

    def test_public_programs_return_confirmed_records_without_admin_fields(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            program_id = self._insert_confirmed_program(db)
            client = TestClient(api.app)

            response = client.get("/public/programs")

        self.assertEqual(response.status_code, 200)
        programs = response.json()
        self.assertEqual(len(programs), 1)
        self.assertEqual(programs[0]["id"], program_id)
        self.assertEqual(programs[0]["school_name"], "明治大学")
        self.assertEqual(programs[0]["faculty"], "理工学部")
        self.assertIn("requirements", programs[0])
        self.assertIn("risk", programs[0])
        for admin_key in ("source_staging_id", "raw_llm_json", "warnings_json", "is_confirmed", "confirmed_by"):
            self.assertNotIn(admin_key, programs[0])

    def test_public_program_detail_and_recommendations_use_confirmed_data(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            program_id = self._insert_confirmed_program(db)
            client = TestClient(api.app)

            detail = client.get(f"/public/programs/{program_id}")
            recommendation = client.post(
                "/public/recommendations",
                json={
                    "target_year": "2027",
                    "desired_fields": ["理工"],
                    "preferred_prefectures": ["東京都"],
                    "english_tests": ["TOEFL"],
                    "eju_subjects": ["日本語", "数学"],
                },
            )
            empty_profile = client.post("/public/recommendations", json={})

        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["id"], program_id)
        self.assertEqual(detail.json()["source_document"]["pdf_url"], "https://example.ac.jp/meiji.pdf")
        self.assertEqual(recommendation.status_code, 200)
        results = recommendation.json()["results"]
        self.assertEqual(results[0]["program"]["id"], program_id)
        self.assertIn(results[0]["fit_level"], {"likely_fit", "check_carefully", "high_risk"})
        self.assertGreater(len(results[0]["reasons"]), 0)
        self.assertIn("check_items", results[0])
        self.assertEqual(empty_profile.status_code, 200)
        self.assertIn("results", empty_profile.json())

    def test_public_booking_requires_contact_and_persists_valid_request(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            program_id = self._insert_confirmed_program(db)
            client = TestClient(api.app)

            missing_contact = client.post(
                "/public/bookings",
                json={
                    "student_name": "王小明",
                    "role": "student",
                    "target_year": "2027",
                    "program_id": program_id,
                    "preferred_times": "周六下午",
                    "question": "想确认EJU要求",
                },
            )
            valid = client.post(
                "/public/bookings",
                json={
                    "student_name": "王小明",
                    "contact_email": "student@example.com",
                    "role": "student",
                    "target_year": "2027",
                    "program_id": program_id,
                    "preferred_times": "周六下午",
                    "question": "想确认EJU要求",
                },
            )
            conn = db.get_conn()
            stored = conn.execute("SELECT * FROM consultation_bookings").fetchall()
            conn.close()

        self.assertEqual(missing_contact.status_code, 400)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()["status"], "received")
        self.assertGreater(valid.json()["id"], 0)
        self.assertEqual(len(stored), 1)

    def test_owner_can_list_and_update_student_booking_requests(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            program_id = self._insert_confirmed_program(db)
            client = TestClient(api.app)

            created = client.post(
                "/public/bookings",
                json={
                    "student_name": "王小明",
                    "contact_email": "student@example.com",
                    "role": "学生本人",
                    "target_year": "2027",
                    "program_id": program_id,
                    "preferred_times": "周六下午",
                    "question": "想确认EJU要求",
                },
            )
            unauth = client.get("/admin/bookings")
            self._login_partner(client)
            partner = client.get("/admin/bookings")
            client.post("/auth/logout")
            self._login_owner(client)
            inbox = client.get("/admin/bookings")
            updated = client.patch(
                f"/admin/bookings/{created.json()['id']}",
                json={
                    "status": "contacted",
                    "owner_note": "先确认EJU成绩，再约家长面谈。",
                    "next_action_at": "2026-06-01 14:00",
                },
            )
            filtered = client.get("/admin/bookings", params={"status": "contacted"})
            searched = client.get("/admin/bookings", params={"status": "contacted", "q": "明治"})
            no_match = client.get("/admin/bookings", params={"status": "contacted", "q": "不存在的学生"})
            exported = client.get("/admin/bookings/export.csv", params={"status": "contacted", "q": "明治"})

        self.assertEqual(created.status_code, 200)
        self.assertEqual(unauth.status_code, 401)
        self.assertEqual(partner.status_code, 403)
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.json()[0]["student_name"], "王小明")
        self.assertEqual(inbox.json()[0]["school_name"], "明治大学")
        self.assertEqual(inbox.json()[0]["faculty"], "理工学部")
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["status"], "contacted")
        self.assertEqual(updated.json()["owner_note"], "先确认EJU成绩，再约家长面谈。")
        self.assertEqual(updated.json()["next_action_at"], "2026-06-01 14:00")
        self.assertEqual(filtered.status_code, 200)
        self.assertEqual(filtered.json()[0]["status"], "contacted")
        self.assertEqual(filtered.json()[0]["owner_note"], "先确认EJU成绩，再约家长面谈。")
        self.assertEqual(searched.status_code, 200)
        self.assertEqual(searched.json()[0]["student_name"], "王小明")
        self.assertEqual(no_match.status_code, 200)
        self.assertEqual(no_match.json(), [])
        self.assertEqual(exported.status_code, 200)
        self.assertIn("text/csv", exported.headers["content-type"])
        self.assertIn("王小明", exported.text)
        self.assertIn("明治大学", exported.text)
        self.assertIn("先确认EJU成绩", exported.text)

    def test_admin_staging_confirm_records_flow_still_works(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            doc_id = db.create_source_document(
                "明治大学",
                "meiji.pdf",
                "/tmp/meiji.pdf",
                "https://example.ac.jp/meiji.pdf",
                "2027",
            )
            db.insert_staging_record(
                doc_id,
                None,
                {
                    "university": "明治大学",
                    "admission_year": "2027",
                    "faculty": "理工学部",
                    "department": "機械工学科",
                    "application_period": "2026年8月25日 - 2026年9月1日",
                    "screening_method": "書類選考",
                    "result_date": "2026年12月3日",
                },
            )
            client = TestClient(api.app)
            self._login_owner(client)

            staging = client.get(f"/staging/{doc_id}")
            confirm = client.post(f"/confirm/{doc_id}")
            records = client.get("/records", params={"university": "明治大学", "year": 2027})

        self.assertEqual(staging.status_code, 200)
        self.assertEqual(len(staging.json()), 1)
        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(confirm.json()["confirmed"], 1)
        self.assertEqual(records.status_code, 200)
        self.assertEqual(len(records.json()), 1)

    def test_owner_routes_require_owner_login_and_partner_has_own_console(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, _db = self._load_api(Path(tmp))
            client = TestClient(api.app)

            unauth_records = client.get("/records")
            self._login_partner(client)
            partner_records = client.get("/records")
            partner_created = client.post(
                "/partner/submissions",
                json={
                    "university": "早稲田大学",
                    "admission_year": "2027",
                    "pdf_url": "https://example.ac.jp/waseda.pdf",
                    "notes": "外国学生入試",
                },
            )
            partner_queue = client.get("/partner/submissions")
            client.post("/auth/logout")
            self._login_owner(client)
            owner_records = client.get("/records")

        self.assertEqual(unauth_records.status_code, 401)
        self.assertEqual(partner_records.status_code, 403)
        self.assertEqual(partner_created.status_code, 200)
        self.assertEqual(partner_queue.status_code, 200)
        self.assertEqual(partner_queue.json()[0]["university"], "早稲田大学")
        self.assertEqual(owner_records.status_code, 200)

    def test_public_program_can_include_safe_quality_metadata_from_staging(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            doc_id = db.create_source_document(
                "明治大学",
                "meiji.pdf",
                "/tmp/meiji.pdf",
                "https://example.ac.jp/meiji.pdf",
                "2027",
            )
            db.insert_staging_record(
                doc_id,
                None,
                {
                    "university": "明治大学",
                    "admission_year": "2027",
                    "faculty": "理工学部",
                    "department": "機械工学科",
                    "application_period": "2026年8月25日 - 2026年9月1日",
                    "screening_method": "書類選考",
                    "result_date": "2026年12月3日",
                    "confidence": 0.82,
                    "risk_level": "medium",
                    "field_evidence": {
                        "application_period": {"text": "2026年8月25日 - 2026年9月1日", "page": 3}
                    },
                    "raw_llm_json": {"internal": True},
                    "warnings_json": ["internal warning"],
                },
            )
            client = TestClient(api.app)
            self._login_owner(client)
            confirm = client.post(f"/confirm/{doc_id}")
            records = client.get("/public/programs")

        self.assertEqual(confirm.status_code, 200)
        self.assertEqual(records.status_code, 200)
        program = records.json()[0]
        self.assertEqual(program["confidence"], 0.82)
        self.assertEqual(program["risk_level"], "medium")
        self.assertEqual(program["risk"]["level"], "medium")
        self.assertEqual(program["evidence"]["application_period"]["page"], 3)
        for admin_key in ("raw_llm_json", "warnings_json", "manual_modified_fields", "confirmed_by"):
            self.assertNotIn(admin_key, program)

    def test_licensed_api_requires_active_scoped_key_and_logs_usage(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            self._insert_confirmed_program(db, university="Meiji University", faculty="Science")
            key = db.issue_api_key(
                organization_name="Tokyo Cram School",
                client_name="Main integration",
                scopes=["programs:read"],
            )
            client = TestClient(api.app)

            no_key = client.get("/v1/programs")
            valid = client.get("/v1/programs", headers={"Authorization": f"Bearer {key['secret']}"})
            denied = client.post(
                "/v1/recommendations",
                headers={"Authorization": f"Bearer {key['secret']}"},
                json={"target_year": "2027", "desired_fields": ["Science"]},
            )
            db.revoke_api_key(int(key["key_id"]))
            revoked = client.get("/v1/programs", headers={"Authorization": f"Bearer {key['secret']}"})
            conn = db.get_conn()
            stored = conn.execute("SELECT key_hash FROM api_key_hashes").fetchall()
            usage = conn.execute("SELECT path, status_code FROM api_usage_logs ORDER BY id").fetchall()
            conn.close()

        self.assertEqual(no_key.status_code, 401)
        self.assertEqual(valid.status_code, 200)
        self.assertEqual(valid.json()[0]["school_name"], "Meiji University")
        self.assertEqual(denied.status_code, 403)
        self.assertEqual(revoked.status_code, 401)
        self.assertEqual(len(stored), 1)
        self.assertNotIn(key["secret"], stored[0]["key_hash"])
        self.assertTrue(any(row["path"] == "/v1/programs" and row["status_code"] == 200 for row in usage))
        self.assertTrue(any(row["path"] == "/v1/recommendations" and row["status_code"] == 403 for row in usage))

    def test_licensed_document_submission_creates_private_queue_item(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            key = db.issue_api_key(
                organization_name="Tokyo Cram School",
                client_name="Submission integration",
                scopes=["documents:submit", "documents:read_status"],
            )
            client = TestClient(api.app)
            self._login_owner(client)

            created = client.post(
                "/v1/documents/submissions",
                headers={"X-API-Key": key["secret"]},
                json={
                    "university": "Waseda University",
                    "admission_year": "2027",
                    "pdf_url": "https://example.ac.jp/admission.pdf",
                    "notes": "Please process this guideline.",
                },
            )
            submission_id = created.json()["id"]
            detail = client.get(
                f"/v1/documents/submissions/{submission_id}",
                headers={"X-API-Key": key["secret"]},
            )
            uploaded = client.post(
                "/v1/documents/submissions",
                headers={"X-API-Key": key["secret"]},
                data={"university": "Keio University", "admission_year": "2027"},
                files={"file": ("keio.pdf", b"%PDF-1.4", "application/pdf")},
            )
            hidden = client.get("/v1/staging/1", headers={"X-API-Key": key["secret"]})

        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["status"], "submitted")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()["processing_status"], "submitted")
        self.assertEqual(uploaded.status_code, 200)
        self.assertEqual(uploaded.json()["processing_status"], "submitted")
        self.assertNotIn("raw_llm_json", detail.json())
        self.assertEqual(hidden.status_code, 404)

    def test_owner_can_manage_submission_queue_without_exposing_private_api_details(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            key = db.issue_api_key(
                organization_name="Tokyo Cram School",
                client_name="Submission integration",
                scopes=["documents:submit", "documents:read_status"],
            )
            client = TestClient(api.app)

            created = client.post(
                "/v1/documents/submissions",
                headers={"X-API-Key": key["secret"]},
                json={
                    "university": "Waseda University",
                    "admission_year": "2027",
                    "pdf_url": "https://example.ac.jp/admission.pdf",
                    "notes": "Please process this guideline.",
                },
            )
            submission_id = created.json()["id"]
            self._login_owner(client)
            queue = client.get("/admin/submissions")
            updated = client.patch(
                f"/admin/submissions/{submission_id}",
                json={"processing_status": "needs_more_info"},
            )

            captured: dict[str, str] = {}

            def fake_workflow(request):
                captured["university"] = request.university
                captured["year"] = request.year
                captured["pdf_url"] = request.pdf_url
                doc_id = db.create_source_document(
                    request.university,
                    "waseda.pdf",
                    "/tmp/waseda.pdf",
                    request.pdf_url,
                    request.year,
                )
                captured["doc_id"] = str(doc_id)
                return {"status": "completed", "doc_id": doc_id, "records": 3, "review_required": True}

            api.run_agent_workflow = fake_workflow
            started = client.post(f"/admin/submissions/{submission_id}/start")
            detail = client.get("/admin/submissions", params={"status": "needs_owner_review"})

        self.assertEqual(queue.status_code, 200)
        self.assertEqual(len(queue.json()), 1)
        self.assertEqual(queue.json()[0]["organization_name"], "Tokyo Cram School")
        self.assertNotIn("api_key_id", queue.json()[0])
        self.assertNotIn("key_hash", str(queue.json()))
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.json()["processing_status"], "needs_more_info")
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["processing_status"], "needs_owner_review")
        self.assertEqual(started.json()["document_id"], int(captured["doc_id"]))
        self.assertEqual(captured["university"], "Waseda University")
        self.assertEqual(captured["year"], "2027")
        self.assertEqual(captured["pdf_url"], "https://example.ac.jp/admission.pdf")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.json()[0]["id"], submission_id)

    def test_browser_smoke_fake_workflow_is_explicitly_gated(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            os.environ["ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW"] = "1"
            api, db = self._load_api(Path(tmp))
            os.environ["ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW"] = "1"
            client = TestClient(api.app)
            self._login_partner(client)
            created = client.post(
                "/partner/submissions",
                json={
                    "university": "東京テスト大学",
                    "admission_year": "2027",
                    "pdf_url": "https://example.edu/browser-smoke.pdf",
                    "notes": "browser smoke",
                },
            )
            submission_id = created.json()["id"]
            client.post("/auth/logout")
            self._login_owner(client)
            started = client.post(f"/admin/submissions/{submission_id}/start")
            staging_rows = db.get_staging_records(started.json()["document_id"])

        os.environ.pop("ADMISSIONS_BROWSER_SMOKE_FAKE_WORKFLOW", None)
        self.assertEqual(started.status_code, 200)
        self.assertEqual(started.json()["processing_status"], "needs_owner_review")
        self.assertEqual(started.json()["workflow_status"], "browser_smoke_completed")
        self.assertGreater(started.json()["document_id"], 0)
        self.assertEqual(len(staging_rows), 1)
        self.assertEqual(staging_rows[0]["faculty"], "ブラウザテスト学部")

    def test_admin_api_center_shows_masked_key_metadata_not_secret(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api, db = self._load_api(Path(tmp))
            key = db.issue_api_key(
                organization_name="Tokyo Cram School",
                client_name="Main integration",
                scopes=["programs:read", "bookings:create", "documents:submit"],
            )
            client = TestClient(api.app)
            client.get("/v1/programs", headers={"Authorization": f"Bearer {key['secret']}"})
            client.post(
                "/v1/documents/submissions",
                headers={"Authorization": f"Bearer {key['secret']}"},
                json={
                    "university": "Waseda University",
                    "admission_year": "2027",
                    "pdf_url": "https://example.ac.jp/admission.pdf",
                },
            )
            self._login_owner(client)

            center = client.get("/settings/api-center")
            created = client.post("/settings/api-keys", json={"client_name": "Second key"})
            refreshed = client.get("/settings/api-center")

        self.assertEqual(center.status_code, 200)
        self.assertIn(center.json()["organization"]["name"], {"Owner Workspace", "Tokyo Cram School"})
        self.assertNotIn(key["secret"], str(center.json()))
        self.assertEqual(created.status_code, 200)
        self.assertIn("secret", created.json())
        self.assertIn("programs:read", created.json()["scopes"])
        self.assertGreaterEqual(len(refreshed.json()["api_keys"]), 1)
        self.assertTrue(refreshed.json()["api_keys"][0]["masked_key"].startswith("ak_"))
        self.assertGreaterEqual(center.json()["usage_summary"]["total"], 2)
        self.assertGreaterEqual(center.json()["usage_summary"]["success"], 2)
        self.assertGreaterEqual(center.json()["usage_summary"]["submission_total"], 1)
        self.assertEqual(center.json()["usage_summary"]["submissions_by_status"]["submitted"], 1)


if __name__ == "__main__":
    unittest.main()
