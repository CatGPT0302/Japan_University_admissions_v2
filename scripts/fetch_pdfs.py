from __future__ import annotations

import argparse
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

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
    Target("立命館大学", "https://admission.ritsumei.ac.jp/application/"),
    Target("大阪大学", "https://www.osaka-u.ac.jp/ja/admissions/faculty/expense/index2.html"),
    Target("上智大学", "https://adm.sophia.ac.jp/jpn/gakubu_tokubetsu_ad/gaikokujin/"),
    Target("九州大学", "https://www.kyushu-u.ac.jp/ja/admission/faculty/selection"),
]

SEARCH_BASE = "https://duckduckgo.com/html/"
KEYWORDS = ("外国人", "留学生", "募集要項")
NEGATIVE_KEYWORDS = (
    "学費",
    "納付",
    "手続",
    "奨学",
    "大学院",
    "編入",
    "過去問",
    "結果",
    "guidebook",
    "overview",
)


def _normalize_name(value: str) -> str:
    return unicodedata.normalize("NFKC", (value or "")).strip()


def _sanitize_filename(name: str) -> str:
    return re.sub(r'[\\/:*?"<>|]+', "_", name)


def _build_search_query(university: str, year: int) -> str:
    return f"{(university or '').strip()} 外国人留学生募集要項 {year}"


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) admissions_v2/1.0",
    }


def _fetch(url: str) -> str:
    resp = requests.get(url, headers=_headers(), timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    return resp.text


def _is_pdf_url(href: str) -> bool:
    lowered = (href or "").lower()
    return lowered.endswith(".pdf") or ".pdf?" in lowered


def _resolve_result_url(href: str) -> str:
    href = (href or "").strip()
    if not href:
        return ""
    parsed = urlparse(href)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        return parse_qs(parsed.query).get("uddg", [href])[0]
    return href


def _score_text(text: str, href: str) -> int:
    combined = f"{text} {href}".lower().replace(" ", "")
    score = 0
    for token in KEYWORDS:
        if token in combined:
            score += 3
    if "pdf" in combined:
        score += 2
    if "入試要項" in combined or "入学試験要項" in combined:
        score += 3
    for token in NEGATIVE_KEYWORDS:
        if token in combined:
            score -= 4
    return score


def _candidate(
    *,
    title: str,
    pdf_url: str,
    page_url: str,
    query: str,
    score: int,
) -> dict[str, str | int]:
    return {
        "title": title.strip() or pdf_url,
        "pdf_url": pdf_url,
        "page_url": page_url,
        "query": query,
        "score": score,
    }


def _dedupe_candidates(candidates: list[dict[str, str | int]]) -> list[dict[str, str | int]]:
    seen: set[str] = set()
    ordered: list[dict[str, str | int]] = []
    for item in sorted(candidates, key=lambda row: int(row.get("score", 0)), reverse=True):
        pdf_url = str(item.get("pdf_url") or "").strip()
        if not pdf_url or pdf_url in seen:
            continue
        seen.add(pdf_url)
        ordered.append(item)
    return ordered


def _discover_pdf_links(page_url: str, html: str, query: str) -> list[dict[str, str | int]]:
    soup = BeautifulSoup(html, "html.parser")
    matches: list[dict[str, str | int]] = []
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        full_url = urljoin(page_url, href)
        if not _is_pdf_url(full_url):
            continue

        pieces = [
            anchor.get_text(" ", strip=True),
            href,
            anchor.parent.get_text(" ", strip=True) if anchor.parent else "",
            anchor.find_parent().get_text(" ", strip=True) if anchor.find_parent() else "",
        ]
        text = " ".join(piece for piece in pieces if piece)
        score = _score_text(text, full_url)
        if score < 3:
            continue
        matches.append(
            _candidate(
                title=text,
                pdf_url=full_url,
                page_url=page_url,
                query=query,
                score=score,
            )
        )
    return _dedupe_candidates(matches)


def _discover_candidate_pages(page_url: str, html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []
    base_host = urlparse(page_url).netloc
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        full_url = urljoin(page_url, href)
        parsed = urlparse(full_url)
        if parsed.netloc and parsed.netloc != base_host:
            continue
        text = " ".join(
            part
            for part in [
                anchor.get_text(" ", strip=True),
                href,
                anchor.parent.get_text(" ", strip=True) if anchor.parent else "",
            ]
            if part
        )
        score = _score_text(text, full_url)
        if score >= 4 and not _is_pdf_url(full_url):
            candidates.append((score, full_url))
    seen: set[str] = set()
    ordered: list[str] = []
    for _, candidate_url in sorted(candidates, key=lambda row: row[0], reverse=True):
        if candidate_url not in seen:
            seen.add(candidate_url)
            ordered.append(candidate_url)
    return ordered[:6]


def _discover_from_page(page_url: str, query: str, depth: int = 0, visited: set[str] | None = None) -> list[dict[str, str | int]]:
    visited = visited or set()
    if page_url in visited or depth > 1:
        return []
    visited.add(page_url)

    html = _fetch(page_url)
    candidates = _discover_pdf_links(page_url, html, query)
    if candidates:
        return candidates

    nested_matches: list[dict[str, str | int]] = []
    for candidate_page in _discover_candidate_pages(page_url, html):
        try:
            nested_matches.extend(_discover_from_page(candidate_page, query, depth + 1, visited))
        except Exception:
            continue
    return _dedupe_candidates(nested_matches)


def _search_result_pages(query: str) -> list[dict[str, str]]:
    resp = requests.get(SEARCH_BASE, params={"q": query}, headers=_headers(), timeout=30)
    resp.raise_for_status()
    resp.encoding = resp.apparent_encoding or resp.encoding
    soup = BeautifulSoup(resp.text, "html.parser")

    results: list[dict[str, str]] = []
    for anchor in soup.select("a.result__a"):
        href = _resolve_result_url(anchor.get("href", ""))
        if not href:
            continue
        title = anchor.get_text(" ", strip=True)
        results.append({"title": title, "url": href})

    if results:
        return results[:8]

    for anchor in soup.find_all("a", href=True):
        href = _resolve_result_url(anchor.get("href", ""))
        title = anchor.get_text(" ", strip=True)
        if not href or not title:
            continue
        if "duckduckgo.com" in urlparse(href).netloc:
            continue
        results.append({"title": title, "url": href})
    return results[:8]


def _download_pdf(url: str, save_path: Path) -> None:
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)


def list_targets() -> list[dict[str, str]]:
    return [{"name": target.name, "url": target.url} for target in TARGETS]


def get_target_by_name(name: str) -> Target | None:
    normalized = _normalize_name(name)
    for target in TARGETS:
        if _normalize_name(target.name) == normalized:
            return target
    return None


def search_single(university: str, year: int, page_url: str = "") -> dict[str, object]:
    university = (university or "").strip()
    page_url = (page_url or "").strip()
    if not university:
        raise ValueError("University is required.")

    query = _build_search_query(university, year)
    candidates: list[dict[str, str | int]] = []

    seed_pages: list[str] = []
    if page_url:
        seed_pages.append(page_url)
    else:
        target = get_target_by_name(university)
        if target:
            seed_pages.append(target.url)

    for seed_page in seed_pages:
        try:
            candidates.extend(_discover_from_page(seed_page, query))
        except Exception:
            continue

    if not candidates:
        for result in _search_result_pages(query):
            result_url = result["url"]
            title = result["title"]
            if _is_pdf_url(result_url):
                score = _score_text(title, result_url)
                if score >= 3:
                    candidates.append(
                        _candidate(
                            title=title,
                            pdf_url=result_url,
                            page_url=result_url,
                            query=query,
                            score=score,
                        )
                    )
                continue
            try:
                candidates.extend(_discover_from_page(result_url, query))
            except Exception:
                continue

    deduped = _dedupe_candidates(candidates)[:8]
    return {
        "university": university,
        "query": query,
        "status": "found" if deduped else "not_found",
        "candidates": deduped,
    }


def fetch_single(university: str, year: int, page_url: str = "", pdf_url: str = "") -> dict[str, str]:
    university = (university or "").strip()
    page_url = (page_url or "").strip()
    pdf_url = (pdf_url or "").strip()

    if not university:
        raise ValueError("University is required.")

    if not pdf_url:
        search_result = search_single(university=university, year=year, page_url=page_url)
        candidates = list(search_result.get("candidates") or [])
        if not candidates:
            return {
                "university": university,
                "status": "not_found",
                "saved_path": "",
                "source_url": page_url,
                "page_url": page_url,
                "query": str(search_result.get("query") or ""),
            }
        first = candidates[0]
        pdf_url = str(first.get("pdf_url") or "")
        page_url = page_url or str(first.get("page_url") or "")

    file_name = f"{_sanitize_filename(university)}_{year}.pdf"
    save_path = INPUT_DIR / file_name
    _download_pdf(pdf_url, save_path)
    return {
        "university": university,
        "status": "downloaded",
        "saved_path": str(save_path),
        "source_url": pdf_url,
        "page_url": page_url or pdf_url,
        "file_name": file_name,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Search or fetch admissions PDFs")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--university", default="", help="University name")
    parser.add_argument("--page-url", default="", help="Optional source page URL")
    parser.add_argument("--pdf-url", default="", help="Optional direct PDF URL")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if not args.university:
        print({"targets": list_targets()})
        return 0

    if args.pdf_url:
        print(fetch_single(args.university, args.year, page_url=args.page_url, pdf_url=args.pdf_url))
        return 0

    print(search_single(args.university, args.year, page_url=args.page_url))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
