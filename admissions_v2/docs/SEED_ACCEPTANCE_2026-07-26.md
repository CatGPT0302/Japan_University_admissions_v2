# Seed Data Acceptance - 2026-07-26

## Scope

This acceptance run used a temporary SQLite database under `.tmp`. It did not
read from or write to `data/admissions.db`.

The tested workflow was:

```text
seed package preview
-> import to staging
-> confirmation blocked before review
-> mark every staging row reviewed through the owner API
-> confirm every source document through the owner API
-> read confirmed data through the public API
-> generate single-school, merged, selected-row Excel, and selected-row CSV exports
```

## Result

- Source documents imported: 18
- Staging rows imported: 81
- Rows reviewed through the owner API: 81
- Confirmation before review: blocked with HTTP 409
- Confirmed records written: 81
- Universities in confirmed records: 18
- Programs returned by `/public/programs`: 81
- Recommendation results returned: 20
- Single-school preview: 12 rows
- Two-school merged preview: 24 rows
- Selected-row preview: 3 rows
- Batch workbook data rows: 24
- Batch workbook sheets: 3
- Excel and CSV responses: successful with download filenames

## Defect Found And Fixed

The first run produced only 79 confirmed records. The confirmation deduplication
key used only university, year, faculty, and department, so two distinct Meiji
admission routes were treated as duplicates.

The record identity now also includes admission period, application period,
screening method, screening schedule, and result date. A regression test covers
distinct routes for the same department.

## Verification

Fresh verification after the fix:

```text
261 passed, 3 skipped
npm run build: passed
npm run smoke:entrypoints: passed
npm run smoke:surfaces: passed
npm run smoke:browser: passed
quality status: quality_gate_ready
seed suite: 18/18 passed
```

## Data Safety

The acceptance database was temporary. Importing the seed package into the
owner's real database remains an explicit owner action and should still begin
with the dry-run preview.
