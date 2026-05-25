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
   - Normalizes full-width and half-width text before substring comparisons, so PDF typography does not create false failures.

5. Narrow deterministic seed extractors
   - `scripts/meiji_schedule_extractor.py`
   - Covers the official Meiji 2027 schedule seed rows that have been checked into `quality_baselines/meiji_2027_schedule.expected.json`.
   - `scripts/waseda_2027_extractor.py`
   - Covers the Waseda 2027 seed rows that have been checked into `quality_baselines/waseda_2027_official.expected.json`.
   - These extractors run only for matching official-source text and should stay narrow.
   - This is a stability anchor, not a full replacement for broader extraction and human review.

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

Run the deterministic seed baseline suite:

```bash
python scripts/quality_baseline_suite.py
```

This checks registered deterministic seed extractors against human-checked baseline files and refuses to treat draft baselines as trusted truth.

Report current quality coverage gaps:

```bash
python scripts/quality_gap_report.py
```

This lists each human-reviewed baseline, whether a local source PDF is available, whether a deterministic seed extractor is registered, and the next action needed to make that baseline enforceable.
Use the `owner_todo` section as the production queue for the next quality pass.
Use each baseline item's `source_candidates` list to place missing PDFs where the quality tools can find them.
Local source PDFs live under ignored folders such as `data/uploads/`; do not commit official PDFs to the repository.
If a university site blocks plain command-line downloads, keep the baseline and seed extractor registered, but leave the local source as missing until a checked PDF is placed in the expected path.

Import a manually downloaded official PDF after checking its content markers:

```bash
python scripts/source_cache.py --source path/to/downloaded.pdf --stem waseda_2027_official --source-url https://www.waseda.jp/inst/admission/assets/uploads/2026/02/01_2027_gaikokugakusei_nyushiyoukou.pdf --marker 早稲田大学 --marker 2027年度
```

The importer copies the PDF into `data/uploads/` and writes a small receipt under `quality_sources/` with the SHA-256 hash, size, source URL, and checked markers. Commit the receipt if useful; do not commit the PDF itself.
`scripts/quality_gap_report.py` includes the receipt in each baseline item when present, but a receipt alone does not make the source available. The local PDF must still exist and pass marker validation.

Run the full owner quality overview:

```bash
python scripts/quality_overview.py
```

This combines the seed baseline suite, the gap report, and the first owner todo into one report.
Use `python scripts/quality_overview.py --summary` for a compact owner-readable status.
The summary separates runnable seed-suite results from registered extractors. For example, an extractor can be registered while its local PDF is still missing.
The JSON output also includes `quality_todo`. Use this to find weakly covered fields, such as `screening_schedule`, that need more human-checked baseline expectations.

Expected baseline files use the PDF stem:

```text
quality_baselines/meiji_2026.expected.json
```

The repository includes a small seed baseline for Waseda 2027:

```text
quality_baselines/waseda_2027_official.expected.json
```

It also includes a small seed baseline for Meiji 2027:

```text
quality_baselines/meiji_2027_schedule.expected.json
```

These seed baselines intentionally cover only a few high-value rows and high-impact items. Extend them after checking more rows against the source PDFs.

## Owner Quality Dashboard

The owner workspace has an `抽取质量` page. It uses:

- `GET /metrics/quality`
- `GET /metrics/corrections`

This page must stay owner-only. It should not appear in the private-school service center or the student/parent frontend.
