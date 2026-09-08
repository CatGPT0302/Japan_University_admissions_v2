"""Loopback-only demo launcher with isolated storage and no external model calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DEMO_ROOT = ROOT / "runtime" / "local_demo"


def demo_environment(root: Path, inherited: dict[str, str]) -> dict[str, str]:
    env = {key: value for key, value in inherited.items()
           if not key.startswith(("PG", "POSTGRES", "RAILWAY", "OPENAI", "LLM", "OWNER_", "PARTNER_"))
           and key not in {"DATABASE_URL", "DATABASE_PUBLIC_URL", "SQLITE_DB_PATH"}}
    for key, relative in {
        "APP_DATA_DIR": "data", "SQLITE_PATH": "data/admissions.db",
        "UPLOAD_DIR": "data/uploads", "EXPORT_DIR": "data/exports",
        "RENDERED_PAGES_DIR": "data/rendered_pages", "LOG_DIR": "logs", "CONFIG_DIR": "config",
    }.items():
        env[key] = str(root / relative)
    env["FRONTEND_DIST_DIR"] = str(ROOT / "frontend" / "dist-demo")
    env["ADMISSIONS_DISABLE_MODEL_CALLS"] = "1"
    env["ADMISSIONS_REQUIRE_HUMAN_REVIEW"] = "1"
    env["ADMISSIONS_LOCAL_LOGIN_ALIAS"] = "demo"
    env["SEED_PACKAGE_DIR"] = str(root / "data" / "exports" / "seed_data_package")
    return env


def load_access(root: Path) -> dict[str, str]:
    root.mkdir(parents=True, exist_ok=True)
    path = root / "access.json"
    try:
        with path.open("x", encoding="utf-8") as handle:
            path.chmod(0o600)
            json.dump({"email": "demo@localhost", "password": secrets.token_urlsafe(24)}, handle)
    except FileExistsError:
        pass
    access = json.loads(path.read_text(encoding="utf-8"))
    if access.get("email") != "demo@localhost" or not access.get("password"):
        raise ValueError(f"Invalid demo credentials in {path}; original accounts will not be used.")
    return access


def reserve_port(preferred: int) -> socket.socket:
    for port in (preferred, 0):
        sock = socket.socket()
        try:
            sock.bind(("127.0.0.1", port))
            sock.listen(128)
            return sock
        except OSError:
            sock.close()
    raise RuntimeError("Cannot reserve a local demo port.")


def build_frontend() -> None:
    node = shutil.which("node")
    bundled = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node"
    if not node and bundled.is_file():
        node = str(bundled)
    frontend = ROOT / "frontend"
    if not node or not (frontend / "node_modules/typescript/bin/tsc").is_file():
        raise RuntimeError("Install Node.js and run npm ci in frontend first; see docs/LOCAL_DEMO.md.")
    env = {**os.environ, "VITE_APP_SURFACE": "owner", "VITE_API_BASE_URL": "same-origin",
           "VITE_ENABLE_STUDENT_ENTRY": "true"}
    subprocess.run([node, "node_modules/typescript/bin/tsc", "-b"], cwd=frontend, env=env, check=True)
    subprocess.run([node, "node_modules/vite/bin/vite.js", "build", "--outDir", "dist-demo"],
                   cwd=frontend, env=env, check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--skip-build", action="store_true", help="Reuse a previously built demo bundle.")
    args = parser.parse_args()
    if not args.skip_build:
        build_frontend()
    if not (ROOT / "frontend/dist-demo/index.html").is_file():
        raise SystemExit("Demo frontend missing. Run again without --skip-build.")
    env = demo_environment(DEFAULT_DEMO_ROOT, dict(os.environ))
    access = load_access(DEFAULT_DEMO_ROOT)
    env.update(OWNER_EMAIL=access["email"], OWNER_PASSWORD=access["password"])
    os.environ.clear()
    os.environ.update(env)
    sys.path.insert(0, str(ROOT))
    # Import after isolation: the app initializes storage at import time.
    import uvicorn
    from scripts.api import app

    sock = reserve_port(args.port)
    port = sock.getsockname()[1]
    print(f"\nLocal demo: http://127.0.0.1:{port}", flush=True)
    print(f"Login details: {DEFAULT_DEMO_ROOT / 'access.json'}", flush=True)
    print("Original database unchanged. External model calls disabled. Ctrl+C to stop.", flush=True)
    try:
        uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port)).run(sockets=[sock])
    finally:
        sock.close()


if __name__ == "__main__":
    main()
