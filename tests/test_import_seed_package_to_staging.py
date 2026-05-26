from __future__ import annotations

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path


class ImportSeedPackageToStagingTest(unittest.TestCase):
    def _reset_db(self, db_path: Path):
        os.environ["SQLITE_PATH"] = str(db_path)
        for name in ("DATABASE_URL", "DATABASE_PUBLIC_URL", "POSTGRES_URL", "POSTGRES_PRISMA_URL", "POSTGRES_URL_NON_POOLING"):
            os.environ.pop(name, None)
        sys.modules.pop("scripts.db", None)
        db = importlib.import_module("scripts.db")
        db.init_db()
        return db

    def _write_package(self, package_dir: Path) -> None:
        package_dir.mkdir(parents=True)
        (package_dir / "documents.json").write_text(
            json.dumps(
                [
                    {
                        "seed_id": "sample-seed",
                        "university": "Sample University",
                        "admission_year": "2027",
                        "source_document": "sample.pdf",
                        "source_url": "https://example.test/sample.pdf",
                        "record_count": 1,
                        "status": "passed",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (package_dir / "records.jsonl").write_text(
            json.dumps(
                {
                    "seed_id": "sample-seed",
                    "seed_record_id": "sample-1",
                    "university": "Sample University",
                    "admission_year": "2027",
                    "faculty": "Letters",
                    "department": "Japanese",
                    "application_period": "2026-09-01 - 2026-09-10",
                    "source_url": "https://example.test/sample.pdf",
                    "database_status": "not_imported",
                },
                ensure_ascii=False,
            )
            + "\n",
            encoding="utf-8",
        )

    def test_dry_run_does_not_mutate_database(self) -> None:
        from scripts.import_seed_package_to_staging import import_seed_package_to_staging

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            package_dir = root / "package"
            self._write_package(package_dir)
            db = self._reset_db(root / "test.db")

            payload = import_seed_package_to_staging(package_dir=package_dir, apply=False)
            conn = db.get_conn()
            documents = conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
            staging = conn.execute("SELECT COUNT(*) FROM admission_records_staging").fetchone()[0]
            conn.close()

        self.assertEqual(payload["summary"]["mode"], "dry_run")
        self.assertEqual(payload["summary"]["records"], 1)
        self.assertEqual(documents, 0)
        self.assertEqual(staging, 0)

    def test_apply_imports_records_to_staging_not_confirmed_records(self) -> None:
        from scripts.import_seed_package_to_staging import import_seed_package_to_staging

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
            root = Path(tmp)
            package_dir = root / "package"
            self._write_package(package_dir)
            db = self._reset_db(root / "test.db")

            payload = import_seed_package_to_staging(package_dir=package_dir, apply=True)
            conn = db.get_conn()
            documents = conn.execute("SELECT COUNT(*) FROM source_documents").fetchone()[0]
            staging_row = conn.execute("SELECT * FROM admission_records_staging").fetchone()
            confirmed = conn.execute("SELECT COUNT(*) FROM admission_records").fetchone()[0]
            conn.close()

        self.assertEqual(payload["summary"]["mode"], "apply")
        self.assertEqual(payload["summary"]["created_documents"], 1)
        self.assertEqual(payload["summary"]["created_staging_records"], 1)
        self.assertEqual(documents, 1)
        self.assertEqual(staging_row["university"], "Sample University")
        self.assertEqual(staging_row["needs_review"], 1)
        self.assertEqual(confirmed, 0)


if __name__ == "__main__":
    unittest.main()
