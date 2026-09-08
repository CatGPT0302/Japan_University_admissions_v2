"""Signup must never grant staff permissions or overwrite an existing account."""
import importlib
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def client(tmp_path, monkeypatch):
    for key in list(__import__("os").environ):
        if key.startswith(("PG", "POSTGRES", "OWNER_", "PARTNER_")) or key in {
            "DATABASE_URL", "DATABASE_PUBLIC_URL", "ADMISSIONS_LOCAL_LOGIN_ALIAS"
        }:
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("SQLITE_PATH", str(tmp_path / "accounts.db"))
    monkeypatch.setenv("OWNER_EMAIL", "demo@localhost")
    monkeypatch.setenv("OWNER_PASSWORD", "owner-test-password")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    for name in ("scripts.api", "scripts.db"):
        sys.modules.pop(name, None)
    api = importlib.import_module("scripts.api")
    with TestClient(api.app) as client:
        yield client


def account(**changes):
    return {"email": "student@example.com", "display_name": "Student", "password": "student123", **changes}


def test_signup_login_logout_and_permissions(client):
    assert client.post("/auth/register", json=account()).status_code == 201
    assert client.get("/auth/me").json()["user"] is None
    result = client.post("/auth/login", json=account())
    assert result.status_code == 200
    assert result.json()["user"]["role"] == "student"
    assert "password" not in str(result.json())
    assert client.get("/auth/me").json()["user"]["email"] == "student@example.com"
    for path in ("/admin/submissions", "/settings/api-center", "/partner/submissions"):
        assert client.get(path).status_code == 403
    assert client.post("/upload", files={"file": ("test.pdf", b"%PDF-1.4", "application/pdf")}).status_code == 403
    assert client.get("/public/programs").status_code == 200
    assert client.post("/auth/logout").status_code == 200
    assert client.get("/auth/me").json()["user"] is None


def test_duplicates_do_not_reset_password_or_role(client):
    assert client.post("/auth/register", json=account()).status_code == 201
    assert client.post("/auth/register", json=account(email=" STUDENT@example.com ", password="changed123")).status_code == 409
    assert client.post("/auth/login", json=account()).status_code == 200
    assert client.post("/auth/login", json=account(password="changed123")).status_code == 401
    # A syntactically valid existing administrator address is equally protected.
    db = importlib.import_module("scripts.db")
    db.upsert_app_user(email="owner@example.com", password="owner-test", role="owner_admin")
    assert client.post("/auth/register", json=account(email="owner@example.com")).status_code == 409
    result = client.post("/auth/login", json={"email": "owner@example.com", "password": "owner-test"})
    assert result.json()["user"]["role"] == "owner_admin"


@pytest.mark.parametrize("changes", [{"role": "owner_admin"}, {"organization_id": 1}, {"password": "123"}, {"email": "demo"}, {"display_name": " "}])
def test_invalid_signup_rejected(client, changes):
    assert client.post("/auth/register", json=account(**changes)).status_code == 422


def test_demo_alias_only_enabled_explicitly(client, monkeypatch):
    credentials = {"email": "demo", "password": "owner-test-password"}
    assert client.post("/auth/login", json=credentials).status_code == 401
    monkeypatch.setenv("ADMISSIONS_LOCAL_LOGIN_ALIAS", "demo")
    assert client.post("/auth/login", json=credentials).json()["user"]["role"] == "owner_admin"


def test_accounts_survive_database_reinitialization(client):
    assert client.post("/auth/register", json=account()).status_code == 201
    importlib.import_module("scripts.db").init_db()
    assert client.post("/auth/login", json=account()).json()["user"]["role"] == "student"

def test_admin_creation_is_explicit_and_never_overwrites(client, monkeypatch):
    import scripts.create_admin as command
    monkeypatch.setattr(sys, "argv", ["create_admin", "--email", "new-owner@example.com"])
    monkeypatch.setattr(command, "getpass", lambda _: "separate-admin-password")
    command.main()
    login = {"email": "new-owner@example.com", "password": "separate-admin-password"}
    assert client.post("/auth/login", json=login).json()["user"]["role"] == "owner_admin"
    monkeypatch.setattr(command, "getpass", lambda _: "replacement-password")
    with pytest.raises(SystemExit, match="already exists"):
        command.main()
    assert client.post("/auth/login", json=login).status_code == 200
