from __future__ import annotations

import os
import sys
from pathlib import Path


SOURCE_ROOT = Path(__file__).resolve().parent.parent


def bundled_root() -> Path:
    """Return the read-only app root when embedded, else the repo root."""
    return Path(getattr(sys, "_MEIPASS", SOURCE_ROOT)).resolve()


def executable_dir() -> Path:
    """Return the writable application directory for the current runtime."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return SOURCE_ROOT


def app_data_dir() -> Path:
    raw = os.environ.get("APP_DATA_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return executable_dir() / "data"


def uploads_dir() -> Path:
    raw = os.environ.get("UPLOAD_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return app_data_dir() / "uploads"


def exports_dir() -> Path:
    raw = os.environ.get("EXPORT_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return app_data_dir() / "exports"


def rendered_pages_dir() -> Path:
    raw = os.environ.get("RENDERED_PAGES_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return app_data_dir() / "rendered_pages"


def logs_dir() -> Path:
    raw = os.environ.get("LOG_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return executable_dir() / "logs"


def config_dir() -> Path:
    raw = os.environ.get("CONFIG_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return executable_dir() / "config"


def sqlite_path() -> Path:
    raw = os.environ.get("SQLITE_PATH", "").strip() or os.environ.get("SQLITE_DB_PATH", "").strip()
    if raw:
        return Path(raw).resolve()
    return app_data_dir() / "admissions.db"


def frontend_dist_dir() -> Path:
    raw = os.environ.get("FRONTEND_DIST_DIR", "").strip()
    if raw:
        return Path(raw).resolve()
    return bundled_root() / "frontend" / "dist"


def ensure_runtime_dirs() -> None:
    for path in (app_data_dir(), uploads_dir(), exports_dir(), rendered_pages_dir(), logs_dir(), config_dir(), sqlite_path().parent):
        path.mkdir(parents=True, exist_ok=True)
