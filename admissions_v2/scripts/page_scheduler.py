from __future__ import annotations

import re
from pathlib import Path


DEFAULT_MAX_PAGES = 12
DEFAULT_KEEP_PAGES = [1]
SKIP_MARKERS = {"目次"}
KEYWORD_WEIGHTS = {
    "入学試験日程": 9,
    "選考方法": 8,
    "日本留学試験": 8,
    "EJU": 8,
    "外国語外部試験": 7,
    "TOEFL": 5,
    "IELTS": 5,
    "２．出願": 10,
    "2.出願": 10,
    "出願期間": 7,
    "出願は": 5,
    "入学手続": 5,
    "合格者発表": 5,
    "出願書類": 4,
}


def parse_page_selection(value: str) -> list[int]:
    pages: set[int] = set()
    for part in re.split(r"[,，\s]+", value.strip()):
        if not part:
            continue
        if "-" in part:
            start_text, end_text = part.split("-", 1)
            if not start_text.strip().isdigit() or not end_text.strip().isdigit():
                continue
            start = int(start_text)
            end = int(end_text)
            if start > end:
                start, end = end, start
            pages.update(range(max(1, start), end + 1))
            continue
        if part.isdigit():
            pages.add(max(1, int(part)))
    return sorted(pages)


def extract_page_texts(pdf_path: Path) -> list[str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        return []
    reader = PdfReader(str(pdf_path))
    return [(page.extract_text() or "") for page in reader.pages]


def score_page(text: str, page_number: int) -> int:
    normalized = re.sub(r"\s+", "", text or "")
    if page_number != 1 and any(marker in normalized for marker in SKIP_MARKERS):
        return -100
    score = 0
    for keyword, weight in KEYWORD_WEIGHTS.items():
        if keyword in normalized:
            score += weight
    # Image-heavy pages often have very little text but are exactly where vision is needed.
    if 40 <= len(normalized) <= 220 and any(marker in normalized for marker in ["入学試験日程", "選考方法"]):
        score += 6
    return score


def select_vision_pages(pdf_path: Path, max_pages: int = DEFAULT_MAX_PAGES, configured_pages: list[int] | None = None) -> list[int] | None:
    if configured_pages:
        return configured_pages

    texts = extract_page_texts(pdf_path)
    if not texts:
        return None

    selected: set[int] = {page for page in DEFAULT_KEEP_PAGES if page <= len(texts)}
    scored: list[tuple[int, int]] = []
    for index, text in enumerate(texts, start=1):
        score = score_page(text, index)
        if score > 0:
            scored.append((score, index))
        # Always keep very low-text table-like pages near admission schedule wording.
        compact = re.sub(r"\s+", "", text or "")
        if index > 1 and 40 <= len(compact) <= 220 and "入学試験日程" in compact:
            selected.add(index)
        if not any(marker in compact for marker in SKIP_MARKERS) and ("２．出願" in compact or compact.startswith("2.出願") or "２.出願" in compact):
            selected.add(index)

    for _score, page_number in sorted(scored, reverse=True):
        selected.add(page_number)
        if len(selected) >= max_pages:
            break

    return sorted(selected) or None
