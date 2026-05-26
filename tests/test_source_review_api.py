from __future__ import annotations

import importlib
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
        self.assertEqual(payload["items"][0]["status"], "changed")
        self.assertIn("confirmed_records_unchanged", payload["items"][0])

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


if __name__ == "__main__":
    unittest.main()
