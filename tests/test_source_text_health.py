from __future__ import annotations


def test_classifies_readable_japanese_admissions_text() -> None:
    from scripts.source_text_health import analyze_text_layer

    report = analyze_text_layer(
        "2027年度 外国人留学生入学試験 募集要項\n"
        "出願期間 2026年9月1日から2026年9月10日まで\n"
        "日本留学試験、JLPT、英語資格の提出が必要です。"
    )

    assert report["status"] == "readable"
    assert report["requires_manual_text_check"] is False
    assert report["japanese_signal_count"] >= 4


def test_classifies_empty_text_layer_as_manual_check_needed() -> None:
    from scripts.source_text_health import analyze_text_layer

    report = analyze_text_layer(" \n\t ")

    assert report["status"] == "empty_text_layer"
    assert report["requires_manual_text_check"] is True
    assert "No usable text" in report["reason"]


def test_classifies_osaka_like_garbled_text_layer_as_manual_check_needed() -> None:
    from scripts.source_text_health import analyze_text_layer

    report = analyze_text_layer(
        "≉ู㑅ᢤ ⚾(오전)እᅜே␃Ꮫ⏕≉ู㑅ᢤ\n"
        "࠙᪥ᮏ␃Ꮫヨ㦂ࠚ ฟ㢪ᮇ㛫 2026ᖺ9᭶1᪥"
    )

    assert report["status"] == "garbled_text_layer"
    assert report["requires_manual_text_check"] is True
    assert report["garbled_signal_count"] >= 5


def test_audits_seed_sources_without_blocking_baseline_status() -> None:
    from scripts.source_text_health import audit_seed_source_text_layers

    report = audit_seed_source_text_layers(
        root=None,
        seeds={
            "readable_seed": {
                "source_candidates": ["readable.pdf"],
            },
            "garbled_seed": {
                "source_candidates": ["garbled.pdf"],
            },
            "missing_seed": {
                "source_candidates": ["missing.pdf"],
            },
        },
        text_by_path={
            "readable.pdf": "外国人留学生 入学試験 出願期間 日本留学試験",
            "garbled.pdf": "≉ู㑅ᢤ እᅜே␃Ꮫ⏕ ࠙᪥ᮏ␃Ꮫヨ㦂ࠚ",
        },
    )

    assert report["passed"] is True
    assert report["summary"]["total"] == 3
    assert report["summary"]["manual_text_check_needed"] == 2
    by_id = {item["id"]: item for item in report["items"]}
    assert by_id["readable_seed"]["text_health"]["status"] == "readable"
    assert by_id["garbled_seed"]["text_health"]["status"] == "garbled_text_layer"
    assert by_id["missing_seed"]["text_health"]["status"] == "missing_source"
