from __future__ import annotations

import hashlib
import json


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


def test_manual_vision_review_receipt_clears_garbled_text_warning(tmp_path) -> None:
    from scripts.source_text_health import audit_seed_source_text_layers

    source_path = tmp_path / "data" / "uploads" / "osaka.pdf"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"official osaka pdf bytes")
    source_hash = hashlib.sha256(source_path.read_bytes()).hexdigest()
    receipt_dir = tmp_path / "quality_sources"
    receipt_dir.mkdir()
    (receipt_dir / "osaka_seed.text_health.json").write_text(
        json.dumps(
            {
                "status": "manual_vision_checked",
                "source_sha256": source_hash,
                "reviewed_pages": ["p.1", "p.3", "p.5", "p.6"],
                "review_note": "Visual review confirmed the table cells needed by the seed baseline.",
            }
        ),
        encoding="utf-8",
    )

    report = audit_seed_source_text_layers(
        root=tmp_path,
        seeds={"osaka_seed": {"stem": "osaka_seed", "source_candidates": ["data/uploads/osaka.pdf"]}},
        text_by_path={
            "data/uploads/osaka.pdf": "\u2400\u2401\u2402\u2403\u2404\u2405\u2406\u2407\u2408\u2409 2027",
        },
    )

    assert report["summary"]["manual_text_check_needed"] == 0
    item = report["items"][0]
    assert item["text_health"]["status"] == "manual_vision_checked"
    assert item["text_health"]["underlying_status"] == "garbled_text_layer"
    assert item["text_health"]["reviewed_pages"] == ["p.1", "p.3", "p.5", "p.6"]


def test_manual_vision_review_receipt_must_match_source_hash(tmp_path) -> None:
    from scripts.source_text_health import audit_seed_source_text_layers

    source_path = tmp_path / "data" / "uploads" / "osaka.pdf"
    source_path.parent.mkdir(parents=True)
    source_path.write_bytes(b"changed pdf bytes")
    receipt_dir = tmp_path / "quality_sources"
    receipt_dir.mkdir()
    (receipt_dir / "osaka_seed.text_health.json").write_text(
        json.dumps(
            {
                "status": "manual_vision_checked",
                "source_sha256": "0" * 64,
                "review_note": "Stale review for another source file.",
            }
        ),
        encoding="utf-8",
    )

    report = audit_seed_source_text_layers(
        root=tmp_path,
        seeds={"osaka_seed": {"stem": "osaka_seed", "source_candidates": ["data/uploads/osaka.pdf"]}},
        text_by_path={
            "data/uploads/osaka.pdf": "\u2400\u2401\u2402\u2403\u2404\u2405\u2406\u2407\u2408\u2409 2027",
        },
    )

    assert report["summary"]["manual_text_check_needed"] == 1
    assert report["items"][0]["text_health"]["manual_review_status"] == "source_hash_mismatch"
