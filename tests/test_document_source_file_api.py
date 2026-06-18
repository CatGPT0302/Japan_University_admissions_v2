from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient


class DocumentSourceFileApiTest(unittest.TestCase):
    def _load_api(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "document_source_file_test.db")
        os.environ["OWNER_EMAIL"] = "owner@example.com"
        os.environ["OWNER_PASSWORD"] = "owner-admin"
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

    def test_document_summary_reports_available_local_source_file(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            api, db = self._load_api(root)
            pdf_path = root / "source.pdf"
            pdf_path.write_bytes(b"%PDF-1.4 local source")
            doc_id = db.create_source_document("Source University", "source.pdf", str(pdf_path), "", "2027")
            client = TestClient(api.app)
            self._login_owner(client)

            response = client.get(f"/documents/{doc_id}/summary")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["source_file_available"])
        self.assertEqual(payload["source_file_message"], "source file is available")

    def test_document_summary_reports_missing_source_file_without_breaking_summary(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            api, db = self._load_api(root)
            doc_id = db.create_source_document("Missing Source University", "missing.pdf", str(root / "missing.pdf"), "", "2027")
            client = TestClient(api.app)
            self._login_owner(client)

            summary_response = client.get(f"/documents/{doc_id}/summary")
            pdf_response = client.get(f"/documents/{doc_id}/pdf")
            image_response = client.get(f"/documents/{doc_id}/page-image?page=1")

        self.assertEqual(summary_response.status_code, 200)
        payload = summary_response.json()
        self.assertEqual(payload["university_name"], "Missing Source University")
        self.assertFalse(payload["source_file_available"])
        self.assertEqual(payload["source_file_message"], "source file is missing")
        self.assertEqual(pdf_response.status_code, 404)
        self.assertEqual(image_response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
