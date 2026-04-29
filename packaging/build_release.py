from __future__ import annotations

import shutil
import subprocess
import sys
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DESKTOP = Path.home() / "Desktop"
RELEASE_DIR = DESKTOP / "格致大学募集要項抽取系统_v1"
EXE_NAME = "v1.exe"


def run(cmd: list[str], cwd: Path = ROOT) -> None:
    print(">", " ".join(cmd))
    subprocess.run(cmd, cwd=cwd, check=True)


def npm_cmd() -> str:
    return "npm.cmd" if os.name == "nt" else "npm"


def ensure_pyinstaller() -> None:
    try:
        subprocess.run([sys.executable, "-m", "PyInstaller", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except Exception as exc:
        raise RuntimeError("PyInstaller is not installed. Run: python -m pip install pyinstaller") from exc


def copy_if_exists(src: Path, dst: Path) -> None:
    if src.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main() -> int:
    ensure_pyinstaller()

    run([npm_cmd(), "run", "build"], cwd=ROOT / "frontend")
    run([sys.executable, "-m", "PyInstaller", "packaging/app.spec", "--noconfirm"], cwd=ROOT)

    built_exe = ROOT / "dist" / EXE_NAME
    if not built_exe.exists():
        raise FileNotFoundError(f"Expected EXE not found: {built_exe}")

    RELEASE_DIR.mkdir(parents=True, exist_ok=True)
    for child in ("data/uploads", "data/exports", "logs", "config"):
        (RELEASE_DIR / child).mkdir(parents=True, exist_ok=True)

    copy_if_exists(built_exe, RELEASE_DIR / EXE_NAME)
    copy_if_exists(built_exe, DESKTOP / EXE_NAME)
    copy_if_exists(ROOT / ".env.example", RELEASE_DIR / ".env.example")
    copy_if_exists(ROOT / "README_使用说明.md", RELEASE_DIR / "README_使用说明.md")
    copy_if_exists(ROOT / ".env.example", DESKTOP / ".env.example")
    copy_if_exists(ROOT / "README_使用说明.md", DESKTOP / "README_使用说明.md")

    print(f"Release folder: {RELEASE_DIR}")
    print(f"Desktop EXE: {DESKTOP / EXE_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
