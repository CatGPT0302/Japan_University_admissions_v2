# Extraction Quality Track

This project treats admissions extraction as a reviewable data-production flow, not a simple OCR task.

## Current Quality Layers

1. Per-record validation
   - `scripts/validator.py`
   - Adds confidence, evidence, review status, warnings, and risk level.

2. Per-document quality gate
   - `scripts/quality_gate.py`
   - Flags parse failure, empty output, truncation, suspicious faculty names, and high missing rates.

3. Human correction feedback
   - `correction_events` in the database.
   - `GET /metrics/quality` and `GET /metrics/corrections` summarize what gets corrected most.

4. Human-reviewed baseline checks
   - `scripts/quality_baseline.py`
   - Compares extracted records against an expected JSON file.
   - Supports exact values, required substrings, any-of checks, and optional empty values.

## Baseline JSON Shape

```json
[
  {
    "id": "waseda-law-2027",
    "match": {
      "university": "早稲田大学",
      "faculty": "法学部",
      "department": "法律学科"
    },
    "expect": {
      "application_period": "2026年6月1日 to 2026年6月8日",
      "eju_session": { "contains": ["2025", "2026"] },
      "english_requirement": { "any_of": ["TOEFL", "IELTS"] },
      "result_date": { "optional": true }
    }
  }
]
```

## Commands

Create a human-review draft from an existing extraction output:

```bash
python scripts/make_quality_baseline_draft.py --input path/to/extracted.json --output quality_baselines/meiji_2027.expected.json
```

Draft files are only review seeds. Keep `review_status: draft_needs_human_check` until the values have been checked against the source PDF.

Compare one extracted output with one expected baseline:

```bash
python scripts/quality_baseline.py --expected path/to/expected.json --extracted path/to/extracted.json
```

Run existing golden-sample coverage reports, and optionally enforce human-reviewed baselines:

```bash
python scripts/regression_golden_samples.py --baseline-dir quality_baselines
```

Run the Waseda 2027 complex-table quality gate:

```bash
python scripts/regression_waseda_2027.py --enforce
```

Expected baseline files use the PDF stem:

```text
quality_baselines/meiji_2026.expected.json
```

The repository includes a small seed baseline for Waseda 2027:

```text
quality_baselines/waseda_2027_official.expected.json
```

It intentionally covers only a few high-value rows and high-impact items. Extend it after checking more rows against the source PDF.

## Owner Quality Dashboard

The owner workspace has an `抽取质量` page. It uses:

- `GET /metrics/quality`
- `GET /metrics/corrections`

This page must stay owner-only. It should not appear in the private-school service center or the student/parent frontend.
