"""The local demo must stop before rendering, persistence, or model transport."""
from pathlib import Path

import pytest

from scripts import full_vision_extractor as extractor


def test_demo_extraction_stops_before_creating_a_document(monkeypatch):
    monkeypatch.setenv("ADMISSIONS_DISABLE_MODEL_CALLS", "1")

    def forbidden(*args, **kwargs):
        pytest.fail("Demo extraction crossed its model boundary")

    monkeypatch.setattr(extractor, "init_db", forbidden)
    monkeypatch.setattr(extractor, "create_source_document", forbidden)
    monkeypatch.setattr(extractor, "_call_llm", forbidden)
    with pytest.raises(RuntimeError, match="Codex"):
        extractor.run_extraction(Path("missing-demo.pdf"), "Example", "2027")


def test_demo_model_transport_stops_before_reading_images(monkeypatch):
    monkeypatch.setenv("ADMISSIONS_DISABLE_MODEL_CALLS", "1")

    def forbidden(*args, **kwargs):
        pytest.fail("Demo tried to prepare a model request")

    monkeypatch.setattr(extractor, "build_prompt", forbidden)
    monkeypatch.setattr(extractor, "_image_data_url", forbidden)
    with pytest.raises(RuntimeError, match="模型 API"):
        extractor._call_llm([Path("missing.png")], "Example", "2027")
