from __future__ import annotations

import asyncio
import logging
import os
import socket
import sys
import threading
import time
import tkinter as tk
import webbrowser
from pathlib import Path
from tkinter import messagebox

import uvicorn

from scripts.runtime_paths import (
    app_data_dir,
    config_dir,
    ensure_runtime_dirs,
    executable_dir,
    exports_dir,
    logs_dir,
    rendered_pages_dir,
    sqlite_path,
    uploads_dir,
)


APP_NAME = "格致大学募集要項抽取系统"
HOST = "127.0.0.1"
PORT = 8000
URL = f"http://{HOST}:{PORT}"


def _load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and value and not os.environ.get(key):
            os.environ[key] = value


def _prepare_runtime() -> Path:
    ensure_runtime_dirs()
    os.environ.setdefault("APP_DATA_DIR", str(app_data_dir()))
    os.environ.setdefault("UPLOAD_DIR", str(uploads_dir()))
    os.environ.setdefault("EXPORT_DIR", str(exports_dir()))
    os.environ.setdefault("RENDERED_PAGES_DIR", str(rendered_pages_dir()))
    os.environ.setdefault("SQLITE_PATH", str(sqlite_path()))
    os.environ.setdefault("LOG_DIR", str(logs_dir()))
    os.environ.setdefault("CONFIG_DIR", str(config_dir()))

    env_path = executable_dir() / ".env"
    example_path = executable_dir() / ".env.example"
    if not env_path.exists() and example_path.exists():
        env_path.write_text(example_path.read_text(encoding="utf-8-sig"), encoding="utf-8")
    _load_env_file(env_path)
    return env_path


def _setup_logging() -> Path:
    log_path = logs_dir() / "app.log"
    logging.basicConfig(
        filename=log_path,
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        encoding="utf-8",
    )
    return log_path


def _port_is_open() -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((HOST, PORT)) == 0


def _has_api_key() -> bool:
    return bool(os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY"))


class LocalApp:
    def __init__(self) -> None:
        self.env_path = _prepare_runtime()
        self.log_path = _setup_logging()
        self.server: uvicorn.Server | None = None
        self.thread: threading.Thread | None = None

        self.root = tk.Tk()
        self.root.title(APP_NAME)
        self.root.geometry("560x360")
        self.root.resizable(False, False)
        self.status = tk.StringVar(value="准备启动本地服务...")
        self.api_key_status = tk.StringVar(value="")
        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self.stop)

    def _build_ui(self) -> None:
        frame = tk.Frame(self.root, padx=24, pady=22)
        frame.pack(fill="both", expand=True)

        tk.Label(frame, text=APP_NAME, font=("Microsoft YaHei UI", 18, "bold")).pack(anchor="w")
        tk.Label(frame, text="本地运行版：上传 PDF、人工复核、确认入库、导出 Excel 主表", font=("Microsoft YaHei UI", 10)).pack(anchor="w", pady=(6, 18))

        tk.Label(frame, textvariable=self.status, font=("Microsoft YaHei UI", 11), fg="#0f172a").pack(anchor="w", pady=(0, 10))
        tk.Label(frame, textvariable=self.api_key_status, font=("Microsoft YaHei UI", 10), fg="#b45309", wraplength=500, justify="left").pack(anchor="w", pady=(0, 18))

        info = (
            f"访问地址：{URL}\n"
            f"数据库：{sqlite_path()}\n"
            f"上传目录：{uploads_dir()}\n"
            f"导出目录：{exports_dir()}\n"
            f"日志：{self.log_path}"
        )
        tk.Label(frame, text=info, font=("Microsoft YaHei UI", 9), justify="left", fg="#475569").pack(anchor="w", pady=(0, 18))

        buttons = tk.Frame(frame)
        buttons.pack(anchor="w", pady=(8, 0))
        tk.Button(buttons, text="打开系统", command=self.open_browser, width=14).pack(side="left", padx=(0, 10))
        tk.Button(buttons, text="打开配置文件", command=self.open_env, width=14).pack(side="left", padx=(0, 10))
        tk.Button(buttons, text="退出程序", command=self.stop, width=14).pack(side="left")

    def start_server(self) -> None:
        if not _has_api_key():
            self.api_key_status.set("提示：尚未配置 API key。可以浏览和复核已有数据；如需抽取 PDF，请先编辑 .env。")
            logging.warning("API key is missing. Extraction will fail until configured.")
        else:
            self.api_key_status.set("API key 已配置。")

        if _port_is_open():
            self.status.set(f"检测到 {PORT} 端口已有服务，已打开浏览器。")
            logging.info("Port %s is already open; opening browser only.", PORT)
            self.open_browser()
            return

        def run() -> None:
            try:
                from scripts.api import app

                config = uvicorn.Config(app, host=HOST, port=PORT, log_level="info", access_log=False, log_config=None)
                self.server = uvicorn.Server(config)
                asyncio.run(self.server.serve())
            except Exception:
                logging.exception("Failed to start local server")
                self.root.after(0, lambda: self.status.set("本地服务启动失败，请查看 logs/app.log。"))

        self.thread = threading.Thread(target=run, name="gezhi-local-server", daemon=True)
        self.thread.start()
        self.root.after(500, self._wait_for_server)

    def _wait_for_server(self, attempts: int = 30) -> None:
        if _port_is_open():
            self.status.set("本地服务已启动，浏览器已打开。")
            logging.info("Local server started at %s", URL)
            self.open_browser()
            return
        if attempts <= 0:
            self.status.set("本地服务启动超时，请查看 logs/app.log。")
            logging.error("Local server startup timed out")
            return
        self.status.set("正在启动本地服务...")
        self.root.after(500, lambda: self._wait_for_server(attempts - 1))

    def open_browser(self) -> None:
        webbrowser.open(URL)

    def open_env(self) -> None:
        try:
            os.startfile(self.env_path)  # type: ignore[attr-defined]
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"无法打开配置文件：{exc}")

    def stop(self) -> None:
        logging.info("Stopping local app")
        if self.server:
            self.server.should_exit = True
        time.sleep(0.2)
        self.root.destroy()

    def run(self) -> None:
        self.start_server()
        self.root.mainloop()


def main() -> int:
    try:
        LocalApp().run()
        return 0
    except Exception as exc:
        try:
            logs_dir().mkdir(parents=True, exist_ok=True)
            (logs_dir() / "app.log").write_text(f"Fatal startup error: {exc}\n", encoding="utf-8")
        except Exception:
            pass
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
