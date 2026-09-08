from scripts.validator import normalize_field_evidence, validate


def test_non_scored_review_fields_keep_their_source_evidence():
    fields = ("university", "admission_year", "admission_period", "faculty", "department",
              "prefecture", "campus", "required_documents", "eligibility", "evidence")
    evidence = {field: {"text": "Source text", "page": 9} for field in fields}
    normalized = normalize_field_evidence({**evidence, "private_notes": "not a data field"})
    for field in fields:
        assert normalized.get(field) == evidence[field]
    assert "private_notes" not in normalized
    result = validate({"field_evidence": evidence})
    for field in fields:
        assert result["field_evidence"].get(field) == evidence[field]
