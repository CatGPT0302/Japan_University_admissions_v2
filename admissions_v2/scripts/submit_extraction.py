"""Submit already-read extraction JSON and its PDF, without calling a model."""
import argparse
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import urllib.error
import urllib.parse
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError("Submission redirects are not allowed")


def submit(package: Path, source: Path, server: str, access_file: Path | None = None):
    url = urllib.parse.urlsplit(server)
    local = url.hostname in {"localhost", "127.0.0.1", "::1"}
    if (url.scheme not in {"http", "https"} or not url.hostname or url.username
            or url.password or url.query or url.fragment or url.path not in {"", "/"}
            or (url.scheme != "https" and not local)):
        raise ValueError("Use an HTTPS server origin, or HTTP on loopback only")
    if access_file and not local:
        raise ValueError("Local demo credentials may only be sent to loopback")
    if package.stat().st_size > 2 * 1024 * 1024 or source.stat().st_size > 50 * 1024 * 1024:
        raise ValueError("Package or PDF exceeds submission limits")
    payload = package.read_bytes()
    json.loads(payload)
    pdf = source.read_bytes()
    opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
    headers = {}
    token = os.environ.get("ADMISSIONS_INGEST_TOKEN", "")
    server = server.rstrip("/")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif access_file:
        access = json.loads(access_file.read_text())
        login = json.dumps({"email": access["email"], "password": access["password"]}).encode()
        with opener.open(urllib.request.Request(server + "/auth/login", data=login,
                         headers={"Content-Type": "application/json"}), timeout=60) as response:
            response.read()
    else:
        raise ValueError("Set ADMISSIONS_INGEST_TOKEN or supply --access-file for a local demo")
    boundary = "admissions-" + secrets.token_hex(24)
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"package\"\r\n\r\n".encode()
            + payload + f"\r\n--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"source.pdf\"\r\nContent-Type: application/pdf\r\n\r\n".encode()
            + pdf + f"\r\n--{boundary}--\r\n".encode())
    headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
    with opener.open(urllib.request.Request(server + "/ingestions", data=body, headers=headers), timeout=120) as response:
        result = json.load(response)
    result["preview_url"] = server + result["preview_url"]
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--source-pdf", type=Path, required=True)
    parser.add_argument("--server", default=os.environ.get("ADMISSIONS_SERVER_URL", "http://127.0.0.1:8765"))
    parser.add_argument("--access-file", type=Path)
    args = parser.parse_args()
    try:
        print(json.dumps(submit(args.package, args.source_pdf, args.server, args.access_file), ensure_ascii=False))
    except (ValueError, OSError, KeyError) as exc:
        parser.exit(1, f"Submission failed: {exc}\n")


if __name__ == "__main__":
    main()
