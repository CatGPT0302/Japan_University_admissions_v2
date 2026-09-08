from __future__ import annotations

import argparse
import csv
import re
import unicodedata
from datetime import datetime
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from scripts.runtime_paths import uploads_dir

ROOT = Path(__file__).resolve().parent.parent
INPUT_DIR = uploads_dir()
INPUT_DIR.mkdir(parents=True, exist_ok=True)

PRIVATE_REGISTRY = ROOT / "private_data" / "pdf_source_registry.csv"
SAMPLE_REGISTRY = ROOT / "data" / "sample_pdf_source_registry.csv"


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


def _headers() -> dict[str, str]:
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) admissions_v2/1.0",
    }


def _build_search_query(university: str, year: int) -> str:
    return f"{(university or '').strip()} 外国人留学生募集要項 {year}"


def _host(url: str) -> str:
    return urlparse(url or "").netloc.lower()


def _is_official_host(host: str) -> bool:
    return host.endswith(".ac.jp") or host.endswith(".edu") or host.endswith(".jp")


def _host_score(host: str) -> int:
    if host.endswith(".ac.jp"):
        return 5
    if host.endswith(".jp"):
        return 3
    if host.endswith(".edu"):
        return 3
    return 0


def _default_source_kind(page_url: str, pdf_url: str) -> str:
    if page_url and page_url == pdf_url:
        return "direct_pdf"
    return "source_page_pdf"


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


def _score_text(university: str, text: str, href: str) -> int:
    combined = f"{text} {href}".lower().replace(" ", "")
    score = 0
    for token in KEYWORDS:
        if token in combined:
            score += 3
    if "外国人留学生募集要項" in combined:
        score += 5
    if "pdf" in combined:
        score += 2
    if "入試要項" in combined or "入学者選抜要項" in combined:
        score += 3
    if _normalize_name(university) and _normalize_name(university).lower() in combined:
        score += 4
    score += _host_score(_host(href))
    for token in NEGATIVE_KEYWORDS:
        if token in combined:
            score -= 4
    return score


def _candidate(
    *,
    title: str,
    university: str,
    pdf_url: str,
    page_url: str,
    query: str,
    score: int,
    source_kind: str | None = None,
    source_origin: str = "auto_search",
    registry_note: str = "",
) -> dict[str, str | int | bool]:
    host = _host(pdf_url)
    return {
        "title": title.strip() or pdf_url,
        "pdf_url": pdf_url,
        "page_url": page_url,
        "query": query,
        "score": score,
        "host": host,
        "is_official": _is_official_host(host),
        "source_kind": source_kind or _default_source_kind(page_url, pdf_url),
        "source_origin": source_origin,
        "registry_note": registry_note,
        "university": university,
    }


def _dedupe_candidates(candidates: list[dict[str, str | int | bool]]) -> list[dict[str, str | int | bool]]:
    seen: set[str] = set()
    ordered: list[dict[str, str | int | bool]] = []
    for item in sorted(candidates, key=lambda row: int(row.get("score", 0)), reverse=True):
        pdf_url = str(item.get("pdf_url") or "").strip()
        if not pdf_url or pdf_url in seen:
            continue
        seen.add(pdf_url)
        ordered.append(item)
    return ordered


def _discover_pdf_links(page_url: str, html: str, query: str, university: str) -> list[dict[str, str | int | bool]]:
    soup = BeautifulSoup(html, "html.parser")
    matches: list[dict[str, str | int | bool]] = []
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
        score = _score_text(university, text, full_url)
        if score < 3:
            continue
        matches.append(
            _candidate(
                title=text,
                university=university,
                pdf_url=full_url,
                page_url=page_url,
                query=query,
                score=score,
            )
        )
    return _dedupe_candidates(matches)


def _discover_candidate_pages(page_url: str, html: str, university: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    candidates: list[tuple[int, str]] = []
    base_host = _host(page_url)
    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        full_url = urljoin(page_url, href)
        parsed_host = _host(full_url)
        if parsed_host and parsed_host != base_host:
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
        score = _score_text(university, text, full_url)
        if score >= 4 and not _is_pdf_url(full_url):
            candidates.append((score, full_url))
    seen: set[str] = set()
    ordered: list[str] = []
    for _, candidate_url in sorted(candidates, key=lambda row: row[0], reverse=True):
        if candidate_url not in seen:
            seen.add(candidate_url)
            ordered.append(candidate_url)
    return ordered[:6]


def _discover_from_page(
    page_url: str,
    query: str,
    university: str,
    depth: int = 0,
    visited: set[str] | None = None,
) -> list[dict[str, str | int | bool]]:
    visited = visited or set()
    if page_url in visited or depth > 1:
        return []
    visited.add(page_url)

    html = _fetch(page_url)
    candidates = _discover_pdf_links(page_url, html, query, university)
    if candidates:
        return candidates

    nested_matches: list[dict[str, str | int | bool]] = []
    for candidate_page in _discover_candidate_pages(page_url, html, university):
        try:
            nested_matches.extend(_discover_from_page(candidate_page, query, university, depth + 1, visited))
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
        if "duckduckgo.com" in _host(href):
            continue
        results.append({"title": title, "url": href})
    return results[:8]


def _download_pdf(url: str, save_path: Path) -> None:
    resp = requests.get(url, headers=_headers(), timeout=60)
    resp.raise_for_status()
    save_path.write_bytes(resp.content)


def _registry_paths() -> list[Path]:
    return [PRIVATE_REGISTRY, SAMPLE_REGISTRY]


@lru_cache(maxsize=1)
def _load_registry_rows() -> tuple[dict[str, str], ...]:
    rows: list[dict[str, str]] = []
    for path in _registry_paths():
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            for raw_row in reader:
                row = {str(key or "").strip(): str(value or "").strip() for key, value in raw_row.items()}
                row["_source_file"] = str(path)
                rows.append(row)
    return tuple(rows)


def _registry_value(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(key, "").strip()
        if value:
            return value
    return ""


def _registry_matches(row: dict[str, str], university: str, year: int) -> bool:
    row_name = _normalize_name(_registry_value(row, "university", "name"))
    if not row_name or row_name != _normalize_name(university):
        return False
    row_year = _registry_value(row, "year", "admission_year")
    return not row_year or row_year == str(year)


def _registry_candidates(university: str, year: int, query: str) -> list[dict[str, str | int | bool]]:
    rows = [row for row in _load_registry_rows() if _registry_matches(row, university, year)]
    candidates: list[dict[str, str | int | bool]] = []
    for index, row in enumerate(rows):
        score_boost = 100 - index
        title = _registry_value(row, "title") or f"{university} 外国人留学生募集要項 {year}"
        pdf_url = _registry_value(row, "pdf_url", "pdf")
        page_url = _registry_value(row, "page_url", "source_page_url", "url")
        note = _registry_value(row, "note", "memo")

        if pdf_url and _is_pdf_url(pdf_url):
            candidates.append(
                _candidate(
                    title=title,
                    university=university,
                    pdf_url=pdf_url,
                    page_url=page_url or pdf_url,
                    query=query,
                    score=score_boost,
                    source_kind="registry_pdf",
                    source_origin="maintained_registry",
                    registry_note=note,
                )
            )
            continue

        if page_url:
            try:
                discovered = _discover_from_page(page_url, query, university)
            except Exception:
                continue
            for discovered_index, item in enumerate(discovered[:4]):
                row_score = score_boost - discovered_index
                candidates.append(
                    _candidate(
                        title=str(item.get("title") or title),
                        university=university,
                        pdf_url=str(item.get("pdf_url") or ""),
                        page_url=page_url,
                        query=query,
                        score=row_score,
                        source_kind="registry_page_pdf",
                        source_origin="maintained_registry",
                        registry_note=note,
                    )
                )
    return _dedupe_candidates(candidates)


def list_targets() -> list[dict[str, str]]:
    return [{"name": target.name, "url": target.url} for target in TARGETS]


def _registry_pdf_urls(university: str, year: int) -> set[str]:
    rows = [row for row in _load_registry_rows() if _registry_matches(row, university, year)]
    urls: set[str] = set()
    for row in rows:
        pdf_url = _registry_value(row, "pdf_url", "pdf")
        if pdf_url and _is_pdf_url(pdf_url):
            urls.add(pdf_url.strip())
    return urls


def probe_targets(year: int = 2026) -> dict[str, object]:
    checked_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    probes: list[dict[str, object]] = []
    for target in TARGETS:
        query = _build_search_query(target.name, year)
        registry_urls = _registry_pdf_urls(target.name, year)
        try:
            candidates = _discover_from_page(target.url, query, target.name)
            top = candidates[0] if candidates else None
            top_pdf = str(top.get("pdf_url") or "") if top else ""
            is_new = bool(top_pdf and top_pdf not in registry_urls)
            status = "ok" if candidates else "no_candidate"
            if is_new:
                status = "new_candidate_detected"
            probes.append(
                {
                    "university": target.name,
                    "seed_url": target.url,
                    "query": query,
                    "status": status,
                    "candidate_count": len(candidates),
                    "top_candidate_pdf": top_pdf,
                    "top_candidate_page": str(top.get("page_url") or "") if top else "",
                    "registry_count": len(registry_urls),
                    "registry_has_top_candidate": bool(top_pdf and top_pdf in registry_urls),
                    "is_new_pdf_candidate": is_new,
                }
            )
        except Exception as exc:
            probes.append(
                {
                    "university": target.name,
                    "seed_url": target.url,
                    "query": query,
                    "status": "error",
                    "candidate_count": 0,
                    "top_candidate_pdf": "",
                    "top_candidate_page": "",
                    "registry_count": len(registry_urls),
                    "registry_has_top_candidate": False,
                    "is_new_pdf_candidate": False,
                    "error": str(exc),
                }
            )
    new_count = sum(1 for item in probes if item.get("is_new_pdf_candidate"))
    error_count = sum(1 for item in probes if item.get("status") == "error")
    return {
        "checked_at": checked_at,
        "year": int(year),
        "target_count": len(TARGETS),
        "new_candidate_count": int(new_count),
        "error_count": int(error_count),
        "probes": probes,
    }


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
    candidates: list[dict[str, str | int | bool]] = []
    candidates.extend(_registry_candidates(university, year, query))

    seed_pages: list[str] = []
    if page_url:
        seed_pages.append(page_url)
    else:
        target = get_target_by_name(university)
        if target:
            seed_pages.append(target.url)

    for seed_page in seed_pages:
        try:
            candidates.extend(_discover_from_page(seed_page, query, university))
        except Exception:
            continue

    if len(_dedupe_candidates(candidates)) < 8:
        for result in _search_result_pages(query):
            result_url = result["url"]
            title = result["title"]
            if _is_pdf_url(result_url):
                score = _score_text(university, title, result_url)
                if score >= 3:
                    candidates.append(
                        _candidate(
                            title=title,
                            university=university,
                            pdf_url=result_url,
                            page_url=result_url,
                            query=query,
                            score=score,
                        )
                    )
                continue
            try:
                candidates.extend(_discover_from_page(result_url, query, university))
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
