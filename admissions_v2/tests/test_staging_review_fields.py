"""The review API must not silently drop editable material/eligibility fields."""
import importlib


def test_staging_response_preserves_materials_eligibility_and_evidence(monkeypatch):
    api = importlib.import_module("scripts.api")
    row = {
        "id": 1, "document_id": 4,
        "eligibility": "Qualification depends on the applicant's education route.",
        "required_documents": "Both score reports must arrive by the deadline.",
        "evidence": "Physical PDF pages 10-12; unresolved conflict requires review.",
        "field_evidence": {"eligibility": {"page": 10, "text": "Source qualification section"}},
        "raw_llm_json": "must not be exposed",
    }
    monkeypatch.setattr(api, "_require_owner", lambda request: None)
    monkeypatch.setattr(api, "get_staging_records", lambda doc_id: [row])
    result = api.list_staging(4, None)[0]
    for field in ("eligibility", "required_documents", "evidence", "field_evidence"):
        assert result.get(field) == row[field]
    assert "raw_llm_json" not in result
