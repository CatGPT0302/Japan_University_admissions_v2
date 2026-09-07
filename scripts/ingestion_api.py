"""Bounded multipart submission; credentials grant ingestion access only."""
import json
import os
import secrets
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi import File, Form, HTTPException, Request, UploadFile

from scripts.ingestion import IngestionConflict, get_ingestion, ingest

MAX_PDF_BYTES = 50 * 1024 * 1024
MAX_PACKAGE_BYTES = 2 * 1024 * 1024


def register_ingestion_routes(app, require_owner, upload_root: Path):
    def authenticate(request):
        expected = os.environ.get("ADMISSIONS_INGEST_TOKEN", "")
        supplied = request.headers.get("authorization", "")
        if expected and secrets.compare_digest(supplied.encode(), f"Bearer {expected}".encode()):
            return
        require_owner(request)

    @app.post("/ingestions")
    async def submit(request: Request, package: str = Form(...), file: UploadFile = File(...)):
        authenticate(request)
        if len(package.encode()) > MAX_PACKAGE_BYTES:
            raise HTTPException(413, "Extraction package is too large")
        work_root = upload_root.parent / "work" / "ingestions"
        work_root.mkdir(parents=True, exist_ok=True)
        try:
            data = json.loads(package)
            with TemporaryDirectory(dir=work_root) as directory:
                source = Path(directory) / "source.pdf"
                size = 0
                with source.open("wb") as output:
                    while chunk := await file.read(1024 * 1024):
                        size += len(chunk)
                        if size > MAX_PDF_BYTES:
                            raise HTTPException(413, "PDF exceeds 50 MiB")
                        output.write(chunk)
                return ingest(data, source, upload_root)
        except IngestionConflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except (ValueError, TypeError) as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            await file.close()

    @app.get("/ingestions/{ingestion_id}")
    def status(ingestion_id: str, request: Request):
        authenticate(request)
        result = get_ingestion(ingestion_id)
        if result is None:
            raise HTTPException(404, "Ingestion not found")
        return result
