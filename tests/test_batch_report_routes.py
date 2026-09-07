from scripts.demo_batch import write_bundle


def test_report_distinguishes_routes_and_escapes_markdown(tmp_path):
    records = []
    for route in ("document-only", "interview | <route>"):
        records.append({
            "university": "Example", "admission_year": "2027",
            "faculty": "Faculty", "department": "Department",
            "admission_period": route, "application_period": "2026-10-01",
            "field_evidence": {}, "warnings": ["Check the source."],
        })
    batch = [{"package": {"document": {"sha256": "a" * 64,
                "source_url": "https://example.edu/source.pdf"}, "records": records}}]
    write_bundle(batch, tmp_path / "report")
    report = (tmp_path / "report/records_readable.md").read_text()
    assert report.count("document-only") == 2
    assert report.count("interview &#124; &lt;route&gt;") == 2
    assert "2026-10-01" in report
