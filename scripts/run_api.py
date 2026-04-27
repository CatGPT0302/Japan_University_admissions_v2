from __future__ import annotations

import multiprocessing
import os
import signal
import sys
import time

import uvicorn


HOST = "0.0.0.0"
PRIMARY_PORT = int(os.environ.get("PORT", "8080"))
FALLBACK_PORT = int(os.environ.get("PORT_FALLBACK", "8000"))


def _ports() -> list[int]:
    ports: list[int] = []
    for port in (PRIMARY_PORT, FALLBACK_PORT):
        if port not in ports:
            ports.append(port)
    return ports


def _serve(port: int) -> None:
    uvicorn.run("scripts.api:app", host=HOST, port=port)


def main() -> int:
    processes = [multiprocessing.Process(target=_serve, args=(port,)) for port in _ports()]

    for process in processes:
        process.start()

    def _shutdown(*_: object) -> None:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=10)
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _shutdown)
    signal.signal(signal.SIGINT, _shutdown)

    try:
        while True:
            for process in processes:
                process.join(timeout=0.2)
                if process.exitcode is not None:
                    exit_code = int(process.exitcode or 0)
                    for other in processes:
                        if other is not process and other.is_alive():
                            other.terminate()
                    for other in processes:
                        if other is not process:
                            other.join(timeout=10)
                    return exit_code
            time.sleep(0.2)
    finally:
        for process in processes:
            if process.is_alive():
                process.terminate()
        for process in processes:
            process.join(timeout=10)


if __name__ == "__main__":
    raise SystemExit(main())
