"""Guard repository entrypoints after consolidating the application directory."""
from pathlib import Path
import json
import tomllib

APP = Path(__file__).resolve().parents[1]
REPO = APP.parent


def test_application_and_deployment_paths():
    assert APP.name == "admissions_v2"
    for path in ("scripts/api.py", "frontend/package.json", "requirements.txt", "start_demo.command"):
        assert (APP / path).is_file()
    docker = (REPO / "Dockerfile").read_text()
    assert "COPY admissions_v2/requirements.txt /app/requirements.txt" in docker
    assert "COPY admissions_v2/ /app/" in docker
    assert "COPY . /app" not in docker
    assert json.loads((REPO / "railway.json").read_text())["build"]["builder"] == "DOCKERFILE"
    assert "cd admissions_v2" in (REPO / "Procfile").read_text()
    config = tomllib.loads((REPO / "nixpacks.toml").read_text())
    assert "admissions_v2/requirements.txt" in config["phases"]["install"]["cmds"][0]
    assert config["start"]["cmd"].startswith("cd admissions_v2 && ")


def test_container_excludes_local_secrets_and_runtime():
    patterns = (REPO / ".dockerignore").read_text().splitlines()
    for pattern in ("**/.venv", "**/runtime", "**/.env", "**/node_modules", "**/*.db", "**/*.pdf"):
        assert pattern in patterns


def test_root_launcher_enters_application():
    launcher = (REPO / "start_demo.command").read_text()
    assert '/admissions_v2"' in launcher
    assert "exec ./start_demo.command" in launcher
