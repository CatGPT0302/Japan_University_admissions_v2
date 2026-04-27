"""
PDF → PNG renderer. Uses pypdfium2 if available, else falls back to pdf2image/poppler.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

def render_pdf_to_images(
    pdf_path: str | Path,
    output_dir: str | Path,
    dpi: int = 200,
    pages: Optional[list[int]] = None,  # 1-indexed; None = all pages
) -> list[Path]:
    """
    Render PDF pages to PNG files.
    Returns list of Path objects in page order.
    """
    source = Path(pdf_path)
    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rendered: list[Path] = []

    # Try pypdfium2 first
    try:
        import pypdfium2 as pdfium
        scale = max(float(dpi) / 72.0, 1.0)
        pdf = pdfium.PdfDocument(str(source))
        try:
            total = len(pdf)
            targets = pages if pages else list(range(1, total + 1))
            for page_num in targets:
                idx = page_num - 1
                if idx < 0 or idx >= total:
                    continue
                page = pdf[idx]
                bitmap = page.render(scale=scale)
                pil_img = bitmap.to_pil()
                out_path = out_dir / f"page_{page_num:03d}.png"
                pil_img.save(out_path, format="PNG", optimize=True)
                rendered.append(out_path)
        finally:
            pdf.close()
        return rendered
    except ImportError:
        pass

    # Fallback: pdf2image (requires poppler)
    try:
        from pdf2image import convert_from_path
        all_images = convert_from_path(str(source), dpi=dpi)
        targets = pages if pages else list(range(1, len(all_images) + 1))
        for page_num in targets:
            idx = page_num - 1
            if idx < 0 or idx >= len(all_images):
                continue
            out_path = out_dir / f"page_{page_num:03d}.png"
            all_images[idx].save(out_path, format="PNG")
            rendered.append(out_path)
        return rendered
    except ImportError:
        pass

    raise RuntimeError(
        "PDF rendering requires pypdfium2 or pdf2image+poppler. "
        "Install with: pip install pypdfium2"
    )
