from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class SourceReviewApiTest(unittest.TestCase):
    def _load_api(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "source_review_api_test.db")
        os.environ["OWNER_EMAIL"] = "owner@example.com"
        os.environ["OWNER_PASSWORD"] = "owner-admin"
        for name in ("DATABASE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
            os.environ.pop(name, None)
        for module_name in ["scripts.api", "scripts.db"]:
            sys.modules.pop(module_name, None)
        return importlib.import_module("scripts.api")

    def _login_owner(self, client: TestClient) -> None:
        response = client.post("/auth/login", json={"email": "owner@example.com", "password": "owner-admin"})
        self.assertEqual(response.status_code, 200)

    def test_source_review_queue_requires_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)

            response = client.get("/admin/source-review-queue")

        self.assertEqual(response.status_code, 401)

    def test_source_review_report_download_requires_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)

            response = client.get("/admin/source-review-report.md")

        self.assertEqual(response.status_code, 401)

    def test_source_watchlist_requires_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)

            response = client.get("/admin/source-watchlist")

        self.assertEqual(response.status_code, 401)

    def test_quality_overview_requires_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)

            response = client.get("/metrics/quality-overview")

        self.assertEqual(response.status_code, 401)

    def test_quality_overview_returns_language_baseline_for_owner(self) -> None:
        report = {
            "overall_status": "quality_gate_ready",
            "language_requirement_coverage": {
                "eju_japanese": {"checked": 8, "passed": 8},
                "jlpt_requirement": {"checked": 2, "passed": 2},
                "english_requirement": {"checked": 6, "passed": 6},
            },
            "per_seed_thin_coverage": [
                {"seed": "sample", "field": "screening_schedule", "checked": 2, "minimum": 3}
            ],
            "source_watchlist": {
                "summary": {
                    "total": 18,
                    "by_type": {"pdf": 17, "html": 1},
                    "metadata_gaps": {"missing_hash": 0},
                }
            },
            "source_review_queue": {
                "summary": {
                    "needs_review": 2,
                    "changed": 1,
                    "failed": 1,
                    "open": 2,
                }
            },
            "quality_todo": [],
            "next_owner_action": None,
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "build_quality_overview", return_value=report):
                response = client.get("/metrics/quality-overview")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["overall_status"], "quality_gate_ready")
        self.assertEqual(payload["language_requirement_coverage"]["eju_japanese"]["checked"], 8)
        self.assertEqual(payload["per_seed_thin_coverage"][0]["field"], "screening_schedule")
        self.assertEqual(payload["source_watchlist_summary"]["total"], 18)
        self.assertEqual(payload["source_review_summary"]["needs_review"], 2)

    def test_source_watchlist_returns_registered_sources_for_owner(self) -> None:
        report = {
            "summary": {
                "total": 1,
                "by_type": {"pdf": 1},
                "metadata_gaps": {
                    "missing_source_url": 0,
                    "missing_source_type": 0,
                    "missing_hash": 1,
                    "missing_last_checked_at": 1,
                    "missing_source_note": 0,
                },
            },
            "items": [
                {
                    "stem": "sample",
                    "id": "sample",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "admission_type": "international_undergraduate",
                    "source_type": "pdf",
                    "source_url": "https://example.test/admissions.pdf",
                    "cached_path": "",
                    "source_candidates": [],
                    "last_known_sha256": "",
                    "last_checked_at": "",
                    "source_note": "Official source",
                    "markers": [],
                    "receipt_status": "",
                }
            ],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "build_watchlist_report", return_value=report):
                response = client.get("/admin/source-watchlist")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["total"], 1)
        self.assertEqual(payload["summary"]["by_type"]["pdf"], 1)
        self.assertEqual(payload["summary"]["metadata_gaps"]["missing_hash"], 1)
        self.assertEqual(payload["items"][0]["university"], "Sample University")

    def test_source_review_queue_returns_human_review_report(self) -> None:
        queue = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "summary": {"needs_review": 1, "changed": 1},
            "items": [
                {
                    "stem": "sample",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "admission_type": "undergraduate",
                    "source_url": "https://example.test/admissions.pdf",
                    "status": "changed",
                    "old_sha256": "aaa",
                    "new_sha256": "bbb",
                    "checked_at": "2026-05-26T00:00:00+00:00",
                    "needs_review": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "load_review_queue", return_value=queue):
                response = client.get("/admin/source-review-queue")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["confirmed_records_unchanged"])
        self.assertEqual(payload["summary"]["needs_review"], 1)
        self.assertEqual(payload["summary"]["open"], 1)
        self.assertEqual(payload["items"][0]["status"], "changed")
        self.assertEqual(payload["items"][0]["review_status"], "open")
        self.assertTrue(payload["items"][0]["item_id"])
        self.assertIn("confirmed_records_unchanged", payload["items"][0])

    def test_source_review_report_can_be_downloaded_as_markdown(self) -> None:
        queue = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "summary": {"needs_review": 1, "changed": 1},
            "items": [
                {
                    "stem": "sample",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "admission_type": "undergraduate",
                    "source_url": "https://example.test/admissions.pdf",
                    "source_type": "pdf",
                    "status": "changed",
                    "old_sha256": "aaaaaaaaaaaa1111",
                    "new_sha256": "bbbbbbbbbbbb2222",
                    "checked_at": "2026-05-26T00:00:00+00:00",
                    "needs_review": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "load_review_queue", return_value=queue):
                response = client.get("/admin/source-review-report.md")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/markdown", response.headers.get("content-type", ""))
        self.assertIn("source-review-report.md", response.headers.get("content-disposition", ""))
        self.assertIn("# 官方来源变化复审报告", response.text)
        self.assertIn("Sample University", response.text)
        self.assertIn("正式资料不会被自动改动", response.text)

    def test_run_source_checks_returns_queue_without_data_update_claims(self) -> None:
        queue = {"generated_at": "2026-05-26T00:00:00+00:00", "summary": {"needs_review": 0}, "items": []}
        check_report = {
            "checked_at": "2026-05-26T00:00:00+00:00",
            "summary": {"total": 1, "unchanged": 1, "needs_review": 0},
            "items": [],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "check_watchlist_sources", return_value=check_report), patch.object(api, "load_review_queue", return_value=queue):
                response = client.post("/admin/source-checks/run", params={"limit": 1})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["unchanged"], 1)
        self.assertTrue(payload["review_queue"]["confirmed_records_unchanged"])

    def test_source_review_item_status_can_be_saved_by_owner(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)
            state_path = Path(tmp) / "states.json"

            with patch.object(api, "update_source_review_state", wraps=lambda item_id, status, note="": __import__(
                "scripts.source_review_state", fromlist=["update_source_review_state"]
            ).update_source_review_state(item_id, status, note=note, path=state_path, now="2026-05-26T00:00:00+00:00")):
                response = client.patch(
                    "/admin/source-review-queue/sample-item",
                    json={"review_status": "needs_reextract", "note": "source changed"},
                )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["item_id"], "sample-item")
        self.assertEqual(payload["review_status"], "needs_reextract")
        self.assertEqual(payload["note"], "source changed")

    def test_source_review_item_status_rejects_unknown_state(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.patch(
                "/admin/source-review-queue/sample-item",
                json={"review_status": "delete_everything"},
            )

        self.assertEqual(response.status_code, 400)

    def test_source_review_item_can_accept_new_source_receipt_without_updating_records(self) -> None:
        queue = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "summary": {"needs_review": 1, "changed": 1},
            "items": [
                {
                    "stem": "sample",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "admission_type": "undergraduate",
                    "source_type": "pdf",
                    "source_url": "https://example.test/admissions.pdf",
                    "status": "changed",
                    "old_sha256": "aaa",
                    "new_sha256": "bbb",
                    "checked_at": "2026-05-26T00:00:00+00:00",
                    "needs_review": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)
            receipt_path = Path(tmp) / "quality_sources" / "sample.source.json"
            receipt_path.parent.mkdir(parents=True)
            receipt_path.write_text(json.dumps({"sha256": "aaa", "source_url": "https://example.test/admissions.pdf"}), encoding="utf-8")
            state_path = Path(tmp) / "states.json"
            report = api.build_change_report(queue, states={})
            item_id = report["items"][0]["item_id"]

            with patch.object(api, "load_review_queue", return_value=queue), patch.object(
                api,
                "accept_source_review_receipt",
                wraps=lambda item: __import__("scripts.source_review_state", fromlist=["accept_source_review_receipt"]).accept_source_review_receipt(
                    item,
                    root=Path(tmp),
                    now="2026-05-26T01:00:00+00:00",
                ),
            ), patch.object(api, "update_source_review_state", wraps=lambda item_id, status, note="": __import__(
                "scripts.source_review_state", fromlist=["update_source_review_state"]
            ).update_source_review_state(item_id, status, note=note, path=state_path, now="2026-05-26T01:00:00+00:00")):
                response = client.post(f"/admin/source-review-queue/{item_id}/accept-source")
            receipt = json.loads(receipt_path.read_text(encoding="utf-8"))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "accepted")
        self.assertTrue(payload["confirmed_records_unchanged"])
        self.assertEqual(payload["receipt"]["old_sha256"], "aaa")
        self.assertEqual(payload["receipt"]["sha256"], "bbb")
        self.assertEqual(receipt["sha256"], "bbb")
        self.assertEqual(receipt["last_accepted_old_sha256"], "aaa")
        self.assertEqual(payload["review_state"]["review_status"], "reviewed")

    def test_source_review_item_can_be_reextracted_without_confirming_records(self) -> None:
        queue = {
            "generated_at": "2026-05-26T00:00:00+00:00",
            "summary": {"needs_review": 1, "changed": 1},
            "items": [
                {
                    "stem": "sample",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "admission_type": "undergraduate",
                    "source_type": "pdf",
                    "source_url": "https://example.test/admissions.pdf",
                    "status": "changed",
                    "old_sha256": "aaa",
                    "new_sha256": "bbb",
                    "checked_at": "2026-05-26T00:00:00+00:00",
                    "needs_review": True,
                }
            ],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)
            report = api.build_change_report(queue, states={})
            item_id = report["items"][0]["item_id"]

            with patch.object(api, "load_review_queue", return_value=queue), patch.object(
                api,
                "run_agent_workflow",
                return_value={
                    "status": "completed",
                    "doc_id": 42,
                    "records": 3,
                    "quality_status": "needs_review",
                    "source": {"selected_pdf_url": "https://example.test/admissions.pdf"},
                },
            ) as workflow, patch.object(api, "update_source_review_state") as update_state:
                response = client.post(f"/admin/source-review-queue/{item_id}/reextract")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["doc_id"], 42)
        self.assertTrue(payload["review_required"])
        self.assertTrue(payload["confirmed_records_unchanged"])
        workflow.assert_called_once()
        request = workflow.call_args.args[0]
        self.assertEqual(request.pdf_url, "https://example.test/admissions.pdf")
        self.assertEqual(request.university, "Sample University")
        self.assertEqual(request.year, "2027")
        update_state.assert_called_once()
        self.assertEqual(update_state.call_args.args[1], "reviewed")

    def test_source_review_reextract_requires_existing_queue_item(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "load_review_queue", return_value={"summary": {"needs_review": 0}, "items": []}):
                response = client.post("/admin/source-review-queue/missing/reextract")

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
