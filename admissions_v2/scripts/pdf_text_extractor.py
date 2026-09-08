"""
PDF text layer extractor.
Extracts raw text per page using pypdfium2 or pdfminer.
Used to supplement vision extraction with accurate text for dates, scores, etc.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any


def extract_text_per_page(pdf_path: str | Path) -> dict[int, str]:
    """
    Returns {page_number: text_content} for all pages.
    page_number is 1-indexed.
    """
    source = Path(pdf_path)

    # Try pypdfium2 first
    try:
        import pypdfium2 as pdfium
        pdf = pdfium.PdfDocument(str(source))
        result = {}
        try:
            for i in range(len(pdf)):
                page = pdf[i]
                text_page = page.get_textpage()
                text = text_page.get_text_range()
                result[i + 1] = text or ""
        finally:
            pdf.close()
        return result
    except ImportError:
        pass

    # Fallback: pdfminer
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LTTextContainer
        result = {}
        for page_num, layout in enumerate(extract_pages(str(source)), start=1):
            texts = []
            for element in layout:
                if isinstance(element, LTTextContainer):
                    texts.append(element.get_text())
            result[page_num] = "\n".join(texts)
        return result
    except ImportError:
        pass

    raise RuntimeError(
        "PDF text extraction requires pypdfium2 or pdfminer.six.\n"
        "Install: pip install pypdfium2"
    )


def extract_page_text(pdf_path: str | Path, page_number: int) -> str:
    """Extract text from a single page (1-indexed)."""
    all_pages = extract_text_per_page(pdf_path)
    return all_pages.get(page_number, "")


def enrich_record_with_text(record: dict[str, Any], page_text: str) -> dict[str, Any]:
    """
    Try to fill empty fields in a record using raw page text.
    Only fills fields that are empty/missing — never overwrites LLM values.
    """
    import re
    r = dict(record)

    # Date patterns
    DATE_RE = re.compile(r"(20\d{2}年\d{1,2}月\d{1,2}日[（(][月火水木金土日][）)]?)")

    # English requirement patterns
    ENGLISH_RE = re.compile(
        r"(TOEFL\s*iBT[\s\S]{0,80}?点以上|IELTS[\s\S]{0,60}?以上|TOEIC[\s\S]{0,60}?以上)",
        re.MULTILINE
    )

    # EJU session pattern
    EJU_SESSION_RE = re.compile(r"(20\d{2}年度第[1-2１２]回)")

    # Fill application_period if empty
    if not str(r.get("application_period") or "").strip():
        dates = DATE_RE.findall(page_text)
        if dates:
            r["application_period"] = dates[0]
            warnings = list(r.get("warnings") or [])
            warnings.append("application_period: テキスト層から補完。要確認。")
            r["warnings"] = warnings
            r["needs_review"] = True

    # Fill eju_session if empty
    if not str(r.get("eju_session") or "").strip():
        sessions = EJU_SESSION_RE.findall(page_text)
        if sessions:
            unique = list(dict.fromkeys(sessions))
            r["eju_session"] = " / ".join(unique[:4])

    # Fill english_requirement if empty
    if not str(r.get("english_requirement") or "").strip():
        matches = ENGLISH_RE.findall(page_text)
        if matches:
            # Clean up whitespace
            cleaned = [re.sub(r"\s+", " ", m).strip() for m in matches[:3]]
            r["english_requirement"] = " / ".join(cleaned)
            warnings = list(r.get("warnings") or [])
            warnings.append("english_requirement: テキスト層から補完。要確認。")
            r["warnings"] = list(dict.fromkeys(warnings))
            r["needs_review"] = True

    return r


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python pdf_text_extractor.py <pdf_path> [page_number]")
        sys.exit(1)
    pdf = Path(sys.argv[1])
    if len(sys.argv) >= 3:
        page = int(sys.argv[2])
        print(f"=== Page {page} ===")
        print(extract_page_text(pdf, page))
    else:
        pages = extract_text_per_page(pdf)
        for p, t in sorted(pages.items()):
            print(f"=== Page {p} ({len(t)} chars) ===")
            print(t[:300])
            print()
