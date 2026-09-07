from pathlib import Path

from scripts.local_demo import demo_environment, load_access, reserve_port


def test_demo_isolates_all_writable_paths_and_external_connections(tmp_path: Path):
    original = {"DATABASE_URL": "postgresql://private/db", "PGHOST": "remote",
                "SQLITE_PATH": "/original.db", "UPLOAD_DIR": "/original/uploads",
                "LLM_API_KEY": "private", "OPENAI_API_KEY": "private",
                "PARTNER_EMAIL": "private@example.com", "PARTNER_PASSWORD": "private"}
    env = demo_environment(tmp_path, original)
    assert env["SQLITE_PATH"] == str(tmp_path / "data" / "admissions.db")
    assert env["UPLOAD_DIR"] == str(tmp_path / "data" / "uploads")
    assert env["ADMISSIONS_DISABLE_MODEL_CALLS"] == "1"
    for key in ("DATABASE_URL", "PGHOST", "LLM_API_KEY", "OPENAI_API_KEY", "PARTNER_EMAIL", "PARTNER_PASSWORD"):
        assert key not in env
    assert original["SQLITE_PATH"] == "/original.db"


def test_demo_credentials_survive_restart_and_are_private(tmp_path: Path):
    first = load_access(tmp_path)
    assert first == load_access(tmp_path)
    assert first["email"] == "demo@localhost"
    assert len(first["password"]) >= 20
    assert (tmp_path / "access.json").stat().st_mode & 0o777 == 0o600


def test_demo_uses_another_port_if_preferred_is_busy():
    first = reserve_port(0)
    try:
        preferred = first.getsockname()[1]
        second = reserve_port(preferred)
        try:
            assert second.getsockname()[1] != preferred
            assert second.getsockname()[0] == "127.0.0.1"
        finally:
            second.close()
    finally:
        first.close()
