# Agent Bootstrap

## Read First

Before changing code, read these files in order:

1. README.md
2. HANDOFF.md
3. docs/handoff.md
4. TODO.md
5. docs/EXTRACTION_QUALITY.md

Only read older demo/spec files when they are directly relevant. Some old notes still describe the repository as a simple extraction MVP; that is no longer the product shape.

## Project Positioning

This is a personal, independent admissions-information system for Japanese university international-student admissions.

It is not a pure OCR project, not an official cram-school product, and not a company internal system. It can support advising workflows, partner submissions, spreadsheet exports, and future notification outputs, but the owner controls the source tracking, extraction workflow, master database, and final confirmation.

## Current Architecture

Keep these surfaces separate:

- Owner/admin workspace: upload/fetch sources, run extraction, review entries, confirm records, export confirmed data, monitor quality and source changes.
- Partner service center: submit materials and see processing progress under owner control.
- Student/parent frontend: profile input, confirmed-only school recommendations, plain-language requirements, consultation booking.

Do not merge these into one hash-route dashboard or expose owner actions from partner/student surfaces.

## Current Priority

Move the project toward a stable owner-operated data product:

- source tracking and source-change review
- reusable, evidence-backed extraction output
- efficient owner review against source PDFs
- confirmed-record search and quick Excel/CSV export
- student-facing confirmed-only recommendations

Small, verified improvements are preferred over large rewrites.

## Do Not Do

Do not:

- rewrite the whole extraction pipeline
- expand seed universities without a coverage reason
- overwrite confirmed data automatically after source changes
- expose internal confidence, evidence, staging, or quality fields to student/partner surfaces
- describe the project as an official school/company/cram-school product
- add multiplier data, payment, calendar, CRM, or full SaaS tenant management without approval
- move files aggressively if that risks breaking existing scripts

## Recommended Next Tasks

Pick one concrete loop and improve it end to end:

1. Source watchlist/change queue: make owner review and re-extraction easier.
2. Review workbench: reduce manual correction time while preserving evidence.
3. Export center: make school/faculty/batch export faster and safer.
4. Student frontend: improve recommendations only from confirmed records.
5. Quality foundation: add checked rows or coverage only when source evidence is available.

## Verification

Normal gate:

```powershell
python -m pytest -q
cd frontend
npm run build
npm run smoke:browser
```

Quality/source gate:

```powershell
python scripts/quality_overview.py --summary
python -m pytest tests/test_check_source_updates.py tests/test_source_change_report.py tests/test_source_review_api.py tests/test_source_watchlist.py -q
```

Always keep the worktree clean after a pushed checkpoint.
