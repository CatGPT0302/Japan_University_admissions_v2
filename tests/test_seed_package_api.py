from __future__ import annotations

import importlib
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient


class SeedPackageApiTest(unittest.TestCase):
    def _load_api(self, tmp_path: Path):
        os.environ["SQLITE_PATH"] = str(tmp_path / "seed_package_api_test.db")
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

    def test_seed_package_endpoints_require_owner_login(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)

            build = client.post("/admin/seed-package/build")
            preview = client.get("/admin/seed-package/import-preview")
            imported = client.post("/admin/seed-package/import", json={"apply": True})

        self.assertEqual(build.status_code, 401)
        self.assertEqual(preview.status_code, 401)
        self.assertEqual(imported.status_code, 401)

    def test_owner_can_build_seed_package_summary_without_returning_all_records(self) -> None:
        package = {
            "summary": {"documents": 1, "records": 2, "database_status": "not_imported"},
            "documents": [
                {
                    "seed_id": "sample-seed",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "record_count": 2,
                    "status": "passed",
                    "failures": [],
                }
            ],
            "records": [{"large": "record"}],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "build_seed_data_package", return_value=package) as build:
                response = client.post("/admin/seed-package/build")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["summary"]["records"], 2)
        self.assertEqual(payload["documents"][0]["seed_id"], "sample-seed")
        self.assertNotIn("records", payload)
        build.assert_called_once()

    def test_seed_package_import_defaults_to_dry_run(self) -> None:
        dry_run_payload = {
            "summary": {
                "mode": "dry_run",
                "documents": 1,
                "records": 2,
                "created_documents": 0,
                "created_staging_records": 0,
                "database_status": "not_imported",
            },
            "items": [],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "import_seed_package_to_staging", return_value=dry_run_payload) as importer:
                response = client.post("/admin/seed-package/import", json={})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["mode"], "dry_run")
        importer.assert_called_once()
        self.assertFalse(importer.call_args.kwargs["apply"])

    def test_seed_package_import_apply_must_be_explicit(self) -> None:
        apply_payload = {
            "summary": {
                "mode": "apply",
                "documents": 1,
                "records": 2,
                "created_documents": 1,
                "created_staging_records": 2,
                "database_status": "staging_imported",
            },
            "items": [],
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            api = self._load_api(Path(tmp))
            client = TestClient(api.app)
            self._login_owner(client)

            with patch.object(api, "import_seed_package_to_staging", return_value=apply_payload) as importer:
                response = client.post("/admin/seed-package/import", json={"apply": True})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["summary"]["created_staging_records"], 2)
        self.assertTrue(importer.call_args.kwargs["apply"])


if __name__ == "__main__":
    unittest.main()
