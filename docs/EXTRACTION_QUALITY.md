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

Compare one extracted output with one expected baseline:

```bash
python scripts/quality_baseline.py --expected path/to/expected.json --extracted path/to/extracted.json
```

Run existing golden-sample coverage reports, and optionally enforce human-reviewed baselines:

```bash
python scripts/regression_golden_samples.py --baseline-dir quality_baselines
```

Expected baseline files use the PDF stem:

```text
quality_baselines/meiji_2026.expected.json
```

## Owner Quality Dashboard

The owner workspace has an `抽取质量` page. It uses:

- `GET /metrics/quality`
- `GET /metrics/corrections`

This page must stay owner-only. It should not appear in the private-school service center or the student/parent frontend.
