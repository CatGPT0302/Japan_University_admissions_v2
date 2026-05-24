from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class AgentWorkflowTest(unittest.TestCase):
    def test_uploaded_file_takes_precedence_and_runs_extraction_without_fetch(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        calls: list[tuple[str, object]] = []

        def fail_search(*args, **kwargs):
            raise AssertionError("search should not run when file_name is supplied")

        def fail_fetch(*args, **kwargs):
            raise AssertionError("fetch should not run when file_name is supplied")

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            calls.append(("extract", pdf_path.name))
            return {
                "doc_id": 17,
                "status": "completed",
                "university": university,
                "records": 3,
                "quality_status": "needs_review",
                "quality_message": "review required",
                "warnings": ["draft"],
            }

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "sample.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(file_name="sample.pdf", university="Example University", year="2027"),
                deps=WorkflowDeps(
                    uploads_dir=upload_dir,
                    search_single=fail_search,
                    fetch_single=fail_fetch,
                    run_extraction=fake_extract,
                ),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["doc_id"], 17)
        self.assertEqual(result["records"], 3)
        self.assertEqual(result["source"]["input_kind"], "file_name")
        self.assertEqual(result["source"]["file_name"], "sample.pdf")
        self.assertEqual(result["draft_json"]["next_step"], "human_review")
        self.assertEqual(calls, [("extract", "sample.pdf")])

    def test_direct_pdf_url_fetches_without_source_search(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        def fail_search(*args, **kwargs):
            raise AssertionError("search should not run for direct pdf_url")

        def fake_fetch(*, university: str, year: int, page_url: str = "", pdf_url: str = ""):
            return {
                "status": "downloaded",
                "file_name": "direct.pdf",
                "saved_path": "",
                "source_url": pdf_url,
                "page_url": page_url or pdf_url,
                "university": university,
            }

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            return {"doc_id": 22, "status": "completed", "records": 1, "warnings": []}

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "direct.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(pdf_url="https://example.ac.jp/direct.pdf", university="Example", year="2027"),
                deps=WorkflowDeps(
                    uploads_dir=upload_dir,
                    search_single=fail_search,
                    fetch_single=fake_fetch,
                    run_extraction=fake_extract,
                ),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"]["input_kind"], "pdf_url")
        self.assertEqual(result["source"]["selected_pdf_url"], "https://example.ac.jp/direct.pdf")

    def test_clear_registry_candidate_auto_selects_and_extracts(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        candidates = [
            {
                "title": "registry pdf",
                "pdf_url": "https://example.ac.jp/registry.pdf",
                "page_url": "https://example.ac.jp/admissions",
                "score": 100,
                "host": "example.ac.jp",
                "is_official": True,
                "source_origin": "maintained_registry",
                "source_kind": "registry_pdf",
            }
        ]

        def fake_search(*, university: str, year: int, page_url: str = ""):
            return {"status": "found", "query": "query", "candidates": candidates}

        def fake_fetch(*, university: str, year: int, page_url: str = "", pdf_url: str = ""):
            return {
                "status": "downloaded",
                "file_name": "registry.pdf",
                "saved_path": "",
                "source_url": pdf_url,
                "page_url": page_url,
                "university": university,
            }

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            return {"doc_id": 23, "status": "completed", "records": 2, "quality_status": "ok", "warnings": []}

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "registry.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(university="Example", year="2027"),
                deps=WorkflowDeps(
                    uploads_dir=upload_dir,
                    search_single=fake_search,
                    fetch_single=fake_fetch,
                    run_extraction=fake_extract,
                ),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"]["selection_reason"], "maintained_registry")
        self.assertEqual(result["source"]["selected_pdf_url"], "https://example.ac.jp/registry.pdf")

    def test_page_url_uses_source_page_before_search_query(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        calls: list[tuple[str, str]] = []
        source_page = "https://example.ac.jp/admissions"

        candidates = [
            {
                "title": "official page pdf",
                "pdf_url": "https://example.ac.jp/page.pdf",
                "page_url": source_page,
                "score": 90,
                "host": "example.ac.jp",
                "is_official": True,
            }
        ]

        def fake_search(*, university: str, year: int, page_url: str = ""):
            calls.append(("search_page_url", page_url))
            return {"status": "found", "query": page_url, "candidates": candidates}

        def fake_fetch(*, university: str, year: int, page_url: str = "", pdf_url: str = ""):
            return {
                "status": "downloaded",
                "file_name": "page.pdf",
                "saved_path": "",
                "source_url": pdf_url,
                "page_url": page_url,
                "university": university,
            }

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            return {"doc_id": 24, "status": "completed", "records": 1, "warnings": []}

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "page.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(page_url=source_page, university="Example", year="2027"),
                deps=WorkflowDeps(
                    uploads_dir=upload_dir,
                    search_single=fake_search,
                    fetch_single=fake_fetch,
                    run_extraction=fake_extract,
                ),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"]["input_kind"], "page_url")
        self.assertEqual(result["source"]["selected_page_url"], source_page)
        self.assertEqual(calls, [("search_page_url", source_page)])

    def test_official_clear_winner_auto_selects_and_extracts(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        candidates = [
            {
                "title": "official winner",
                "pdf_url": "https://example.ac.jp/winner.pdf",
                "page_url": "https://example.ac.jp/admissions",
                "score": 97,
                "host": "example.ac.jp",
                "is_official": True,
            },
            {
                "title": "official lower score",
                "pdf_url": "https://example.ac.jp/lower.pdf",
                "page_url": "https://example.ac.jp/other",
                "score": 89,
                "host": "example.ac.jp",
                "is_official": True,
            },
        ]

        def fake_search(*, university: str, year: int, page_url: str = ""):
            return {"status": "found", "query": "query", "candidates": candidates}

        def fake_fetch(*, university: str, year: int, page_url: str = "", pdf_url: str = ""):
            return {
                "status": "downloaded",
                "file_name": "winner.pdf",
                "saved_path": "",
                "source_url": pdf_url,
                "page_url": page_url,
                "university": university,
            }

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            return {"doc_id": 25, "status": "completed", "records": 2, "warnings": []}

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "winner.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(university="Example", year="2027"),
                deps=WorkflowDeps(
                    uploads_dir=upload_dir,
                    search_single=fake_search,
                    fetch_single=fake_fetch,
                    run_extraction=fake_extract,
                ),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["source"]["selection_reason"], "official_clear_winner")
        self.assertEqual(result["source"]["selected_pdf_url"], "https://example.ac.jp/winner.pdf")

    def test_ambiguous_candidates_require_source_confirmation_without_extracting(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        candidates = [
            {"title": "A", "pdf_url": "https://a.ac.jp/a.pdf", "page_url": "https://a.ac.jp", "score": 16, "is_official": True},
            {"title": "B", "pdf_url": "https://b.ac.jp/b.pdf", "page_url": "https://b.ac.jp", "score": 15, "is_official": True},
        ]

        def fake_search(*, university: str, year: int, page_url: str = ""):
            return {"status": "found", "query": "query", "candidates": candidates}

        def fail_fetch(*args, **kwargs):
            raise AssertionError("fetch should not run when source selection is ambiguous")

        def fail_extract(*args, **kwargs):
            raise AssertionError("extract should not run when source selection is ambiguous")

        result = run_agent_workflow(
            AgentRequest(university="Example", year="2027"),
            deps=WorkflowDeps(search_single=fake_search, fetch_single=fail_fetch, run_extraction=fail_extract),
        )

        self.assertEqual(result["status"], "needs_source_confirmation")
        self.assertEqual(result["university"], "Example")
        self.assertEqual(result["year"], "2027")
        self.assertEqual(len(result["candidates"]), 2)

    def test_successful_workflow_does_not_auto_confirm_records(self) -> None:
        from scripts.agent_workflow import AgentRequest, WorkflowDeps, run_agent_workflow

        def fake_extract(*, pdf_path: Path, university: str, year: str, url: str):
            return {
                "doc_id": 31,
                "status": "completed",
                "records": 4,
                "quality_status": "needs_review",
                "quality_message": "needs review",
                "warnings": [],
            }

        def fail_confirm(*args, **kwargs):
            raise AssertionError("agent workflow must not auto-confirm records")

        with tempfile.TemporaryDirectory() as tmp:
            upload_dir = Path(tmp)
            (upload_dir / "sample.pdf").write_bytes(b"%PDF-1.4")
            result = run_agent_workflow(
                AgentRequest(file_name="sample.pdf", university="Example", year="2027"),
                deps=WorkflowDeps(uploads_dir=upload_dir, run_extraction=fake_extract, confirm_all_by_doc=fail_confirm),
            )

        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["draft_json"]["review_required"], True)
        self.assertEqual(result["draft_json"]["next_step"], "human_review")


if __name__ == "__main__":
    unittest.main()
