from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = ROOT / "input_pdfs"
INPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class Target:
    name: str
    url: str


TARGETS = [
    Target("明治大学", "https://www.meiji.ac.jp/cip/prospective/admission_exams/ug_application.html"),
    Target("立命館大学", "https://admission.ritsumei.ac.jp/"),
    Target("大阪大学", "https://www.osaka-u.ac.jp/ja/admissions/faculty/expense/index2.html"),
    Target("上智大学", "https://adm.sophia.ac.jp/jpn/gakubu_tokubetsu_ad/gaikokujin/"),
    Target("九州大学", "https://www.kyushu-u.ac.jp/ja/admission/faculty/selection"),
]

KEYWORDS = ("外国人留学生", "募集要項")


def _fetch(url: str) -> str:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) admissions_v2/1.0",
    }
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def _is_pdf_url(href: str) -> bool:
    href_lower = href.lower()
    return href_lower.endswith(".pdf") or ".pdf?" in href_lower or "pdf" in href_lower


def _looks_relevant(text: str) -> bool:
    lowered = text.replace(" ", "")
    return all(keyword in lowered for keyword in KEYWORDS)


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name)


def _normalize_name(value: str) -> str:
    return unicodedata.normalize("NFKC", (value or "")).strip()


def _discover_pdf_links(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    matches: list[str] = []

    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(page_url, href)
        if not _is_pdf_url(full_url):
            continue

        pieces = [
            a.get_text(" ", strip=True),
            href,
            a.parent.get_text(" ", strip=True) if a.parent else "",
            a.find_parent().get_text(" ", strip=True) if a.find_parent() else "",
        ]
        text = " ".join(piece for piece in pieces if piece)
        if _looks_relevant(text):
            matches.append(full_url)

    deduped = []
    seen = set()
    for link in matches:
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped


def _discover_candidate_pages(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[str] = []
    base_host = urlparse(page_url).netloc
    for a in soup.find_all("a", href=True):
        href = a["href"].strip()
        full_url = urljoin(page_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc and parsed.netloc != base_host:
            continue
        text = " ".join(
            part for part in [
                a.get_text(" ", strip=True),
                href,
                a.parent.get_text(" ", strip=True) if a.parent else "",
            ]
            if part
        )
        if _looks_relevant(text) and not _is_pdf_url(full_url):
            candidates.append(full_url)
    deduped = []
    seen = set()
    for link in candidates:
        if link not in seen:
            seen.add(link)
            deduped.append(link)
    return deduped


def _download_pdf(url: str, save_path: Path) -> None:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) admissions_v2/1.0",
    }
    resp = requests.get(url, headers=headers, timeout=60)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)


def fetch_target(target: Target, year: int) -> dict:
    html = _fetch(target.url)
    links = _discover_pdf_links(target.url, html)
    if not links:
        for candidate in _discover_candidate_pages(target.url, html):
            try:
                nested_html = _fetch(candidate)
            except Exception:
                continue
            links = _discover_pdf_links(candidate, nested_html)
            if links:
                break
    if not links:
        return {"university": target.name, "status": "not_found", "saved_path": "", "source_url": target.url}

    pdf_url = links[0]
    file_name = f"{_sanitize_filename(target.name)}_{year}.pdf"
    save_path = INPUT_DIR / file_name
    _download_pdf(pdf_url, save_path)
    return {
        "university": target.name,
        "status": "downloaded",
        "saved_path": str(save_path),
        "source_url": pdf_url,
    }


def list_targets() -> list[dict[str, str]]:
    return [{"name": target.name, "url": target.url} for target in TARGETS]


def get_target_by_name(name: str) -> Target | None:
    normalized = _normalize_name(name)
    for target in TARGETS:
        if _normalize_name(target.name) == normalized:
            return target
    return None


def fetch_single(university: str, year: int, page_url: str = "") -> dict:
    university = (university or "").strip()
    page_url = (page_url or "").strip()

    if not university:
        raise ValueError("University is required.")

    if page_url:
        target = Target(university, page_url)
    else:
        target = get_target_by_name(university)
        if target is None:
            raise ValueError("No preset source found for this university. Please provide a source page URL.")

    result = fetch_target(target, year)
    result["page_url"] = target.url
    if result.get("saved_path"):
        result["file_name"] = Path(result["saved_path"]).name
    return result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch admissions PDFs")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--university", default="", help="Optional single university name")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    targets = TARGETS
    if args.university:
        targets = [t for t in TARGETS if t.name == args.university]
    if not targets:
        print("No matching university found.")
        return 1

    results = []
    for target in targets:
        try:
            result = fetch_target(target, args.year)
        except Exception as exc:
            result = {
                "university": target.name,
                "status": "error",
                "error": str(exc),
                "source_url": target.url,
            }
        results.append(result)
        print(result)

    print({"saved_count": sum(1 for r in results if r.get("status") == "downloaded")})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
