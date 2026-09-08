from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts import fetch_pdfs  # noqa: E402
from scripts import full_vision_extractor  # noqa: E402
from scripts.runtime_paths import exports_dir, uploads_dir  # noqa: E402


SearchSingle = Callable[..., dict[str, Any]]
FetchSingle = Callable[..., dict[str, Any]]
RunExtraction = Callable[..., dict[str, Any]]
ConfirmAllByDoc = Callable[..., dict[str, Any]]

AUTO_SELECT_SCORE_GAP = 5


@dataclass(frozen=True)
class AgentRequest:
    file_name: str = ""
    pdf_url: str = ""
    page_url: str = ""
    university: str = ""
    year: str = "2026"
    draft_output: Path | None = None


@dataclass(frozen=True)
class WorkflowDeps:
    uploads_dir: Path = field(default_factory=uploads_dir)
    search_single: SearchSingle = fetch_pdfs.search_single
    fetch_single: FetchSingle = fetch_pdfs.fetch_single
    run_extraction: RunExtraction = full_vision_extractor.run_extraction
    confirm_all_by_doc: ConfirmAllByDoc | None = None


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _year_as_int(year: str) -> int:
    text = _clean(year) or "2026"
    try:
        return int(text)
    except ValueError as exc:
        raise ValueError(f"Invalid admission year: {year}") from exc


def _candidate_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    candidates = [dict(item) for item in value if isinstance(item, dict)]
    return sorted(candidates, key=lambda item: int(item.get("score") or 0), reverse=True)


def _source_origin(candidate: dict[str, Any]) -> str:
    return _clean(candidate.get("source_origin"))


def _source_kind(candidate: dict[str, Any]) -> str:
    return _clean(candidate.get("source_kind"))


def _is_official(candidate: dict[str, Any]) -> bool:
    return bool(candidate.get("is_official"))


def _score(candidate: dict[str, Any]) -> int:
    try:
        return int(candidate.get("score") or 0)
    except Exception:
        return 0


def _trim_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "title",
        "pdf_url",
        "page_url",
        "query",
        "score",
        "host",
        "is_official",
        "source_kind",
        "source_origin",
        "registry_note",
        "university",
    )
    return {key: candidate.get(key, "") for key in keys if key in candidate}


def _select_candidate(candidates: list[dict[str, Any]]) -> tuple[dict[str, Any] | None, str]:
    if not candidates:
        return None, "no_candidates"
    top = candidates[0]
    origin = _source_origin(top)
    kind = _source_kind(top)
    if origin == "maintained_registry" or kind.startswith("registry_"):
        return top, "maintained_registry"

    second = candidates[1] if len(candidates) > 1 else None
    gap = _score(top) - _score(second) if second else AUTO_SELECT_SCORE_GAP
    if _is_official(top) and gap >= AUTO_SELECT_SCORE_GAP:
        return top, "official_clear_winner"
    return None, "ambiguous_candidates"


def _source_report(
    *,
    input_kind: str,
    file_name: str = "",
    selected_pdf_url: str = "",
    selected_page_url: str = "",
    selection_reason: str = "",
    candidates: list[dict[str, Any]] | None = None,
    query: str = "",
) -> dict[str, Any]:
    return {
        "input_kind": input_kind,
        "file_name": file_name,
        "selected_pdf_url": selected_pdf_url,
        "selected_page_url": selected_page_url,
        "selection_reason": selection_reason,
        "query": query,
        "candidates": [_trim_candidate(candidate) for candidate in candidates or []],
    }


def _resolve_uploaded_file(request: AgentRequest, deps: WorkflowDeps) -> tuple[Path, dict[str, Any]]:
    file_name = Path(request.file_name).name
    pdf_path = deps.uploads_dir / file_name
    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_name}")
    return pdf_path, _source_report(input_kind="file_name", file_name=file_name, selection_reason="uploaded_file")


def _fetch_direct_pdf(request: AgentRequest, deps: WorkflowDeps, year_int: int) -> tuple[Path, dict[str, Any]]:
    result = deps.fetch_single(
        university=request.university,
        year=year_int,
        page_url=request.page_url,
        pdf_url=request.pdf_url,
    )
    if result.get("status") != "downloaded":
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    file_name = Path(_clean(result.get("file_name"))).name
    saved_path = Path(_clean(result.get("saved_path"))) if _clean(result.get("saved_path")) else deps.uploads_dir / file_name
    return saved_path, _source_report(
        input_kind="pdf_url",
        file_name=file_name,
        selected_pdf_url=request.pdf_url,
        selected_page_url=_clean(result.get("page_url")) or request.pdf_url,
        selection_reason="direct_pdf_url",
    )


def _resolve_candidate_source(
    request: AgentRequest,
    deps: WorkflowDeps,
    year_int: int,
) -> tuple[Path | None, dict[str, Any], dict[str, Any] | None]:
    search_result = deps.search_single(
        university=request.university,
        year=year_int,
        page_url=request.page_url,
    )
    candidates = _candidate_list(search_result.get("candidates"))
    selected, reason = _select_candidate(candidates)
    source = _source_report(
        input_kind="page_url" if request.page_url else "search",
        candidates=candidates,
        query=_clean(search_result.get("query")),
        selection_reason=reason,
    )
    if selected is None:
        return None, source, {
            "status": "needs_source_confirmation",
            "university": request.university,
            "year": request.year,
            "candidates": source["candidates"],
            "source": source,
        }

    pdf_url = _clean(selected.get("pdf_url"))
    page_url = _clean(selected.get("page_url")) or request.page_url
    result = deps.fetch_single(
        university=request.university,
        year=year_int,
        page_url=page_url,
        pdf_url=pdf_url,
    )
    if result.get("status") != "downloaded":
        raise RuntimeError(json.dumps(result, ensure_ascii=False))
    file_name = Path(_clean(result.get("file_name"))).name
    saved_path = Path(_clean(result.get("saved_path"))) if _clean(result.get("saved_path")) else deps.uploads_dir / file_name
    source.update(
        {
            "file_name": file_name,
            "selected_pdf_url": pdf_url,
            "selected_page_url": page_url,
            "selection_reason": reason,
        }
    )
    return saved_path, source, None


def _resolve_source(request: AgentRequest, deps: WorkflowDeps) -> tuple[Path | None, dict[str, Any], dict[str, Any] | None]:
    year_int = _year_as_int(request.year)
    if request.file_name:
        pdf_path, source = _resolve_uploaded_file(request, deps)
        return pdf_path, source, None
    if request.pdf_url:
        pdf_path, source = _fetch_direct_pdf(request, deps, year_int)
        return pdf_path, source, None
    if not request.university:
        raise ValueError("university is required when file_name or pdf_url is not supplied")
    return _resolve_candidate_source(request, deps, year_int)


def _draft_json(result: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": result.get("status", "completed"),
        "doc_id": result.get("doc_id"),
        "source": source,
        "records": result.get("records", 0),
        "quality_status": result.get("quality_status", "needs_review"),
        "quality_message": result.get("quality_message", ""),
        "warnings": list(result.get("warnings") or []),
        "review_required": True,
        "next_step": "human_review",
    }


def run_agent_workflow(request: AgentRequest, deps: WorkflowDeps | None = None) -> dict[str, Any]:
    deps = deps or WorkflowDeps()
    pdf_path, source, pending = _resolve_source(request, deps)
    if pending is not None:
        return pending
    assert pdf_path is not None
    result = deps.run_extraction(
        pdf_path=pdf_path,
        university=request.university,
        year=str(request.year),
        url=_clean(source.get("selected_pdf_url")),
    )
    draft = _draft_json(result, source)
    response = {
        "status": result.get("status", "completed"),
        "doc_id": result.get("doc_id"),
        "source": source,
        "records": result.get("records", 0),
        "quality_status": result.get("quality_status", "needs_review"),
        "quality_message": result.get("quality_message", ""),
        "warnings": list(result.get("warnings") or []),
        "draft_json": draft,
    }
    return response


def _write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one agentic admissions PDF workflow.")
    parser.add_argument("--file-name", default="", help="Existing uploaded PDF file name.")
    parser.add_argument("--pdf-url", default="", help="Direct PDF URL.")
    parser.add_argument("--page-url", default="", help="Source page URL.")
    parser.add_argument("--university", default="", help="University name.")
    parser.add_argument("--year", required=True, help="Admission year.")
    parser.add_argument("--draft-output", type=Path, default=None, help="Optional JSON output path.")
    return parser


def main() -> int:
    from scripts.db import init_db

    args = build_parser().parse_args()
    init_db()
    request = AgentRequest(
        file_name=args.file_name,
        pdf_url=args.pdf_url,
        page_url=args.page_url,
        university=args.university,
        year=args.year,
        draft_output=args.draft_output,
    )
    result = run_agent_workflow(request)
    output_path = args.draft_output
    if output_path is None and result.get("status") != "needs_source_confirmation":
        doc_id = result.get("doc_id") or "unknown"
        output_path = exports_dir() / f"agent_draft_{doc_id}.json"
    if output_path is not None:
        _write_json(output_path, result.get("draft_json") or result)
        result["draft_output"] = str(output_path)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result.get("status") != "failed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
