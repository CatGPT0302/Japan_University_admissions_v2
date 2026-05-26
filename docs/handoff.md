# Current Handoff

## Project Positioning

This is a personal, owner-hosted Japanese university admissions information system for international-student admissions.

The core problem is scattered, year-sensitive official admissions information across university pages and PDFs. The project turns those sources into source-tracked, reviewable, searchable, exportable admissions data.

Do not describe this as an official company, cram-school, or WeCom product. It can support advising workflows and partner usage, but ownership, data assets, extraction control, and final confirmation stay with the owner.

## Current Product Shape

The repository now supports separate surfaces:

1. Owner/admin workspace
   - Upload or fetch admissions materials.
   - Run extraction.
   - Review extracted entries against source PDFs.
   - Confirm records into the main database.
   - Search and export confirmed admissions data.
   - Monitor source changes and extraction quality.

2. Owner partner-management / partner service center
   - Partner users can submit source links or PDFs.
   - Owner/admin controls processing and final confirmation.
   - Partner users do not own the master database and cannot confirm records or export the full database.

3. Student/parent frontend
   - Users enter a profile.
   - The app shows schools worth checking and plain-language requirements.
   - Users can book a consultation.
   - Student-facing UI must not expose internal quality, evidence, staging, or review terms.

Keep these surfaces visually, semantically, and operationally separate.

## Current Quality State

The current quality overview command is:

```powershell
python scripts/quality_overview.py --summary
```

Recent known status:

- seed suite: 18/18 passed
- baseline files: 18
- registered extractors: 18
- missing local sources: 0
- watched sources: 18
- source review queue: 0 needing review

Treat the work as a source-tracked data production system, not just a UI shell.

## Current High-Value Work

Prefer changes that improve one of these loops:

- source watchlist -> change detection -> owner review
- extraction -> staging -> field evidence -> human correction -> confirm
- confirmed records -> search/filter -> quick export
- export preview -> source review handoff
- student profile -> confirmed-only recommendation -> consultation booking

## Do Not Do Without Asking

- Do not rewrite the extraction pipeline.
- Do not expand seed universities blindly.
- Do not claim final eligibility guarantees.
- Do not claim official affiliation with any school or company.
- Do not automatically overwrite confirmed records when a source changes.
- Do not expose internal review, confidence, evidence, or full database exports to partner users or students.
- Do not add login/payment/calendar/CRM expansion unless explicitly approved.

## Verification

Use these checks for normal development:

```powershell
python -m pytest -q
cd frontend
npm run build
npm run smoke:browser
```

For source and quality work, also run:

```powershell
python scripts/quality_overview.py --summary
python -m pytest tests/test_check_source_updates.py tests/test_source_change_report.py tests/test_source_review_api.py tests/test_source_watchlist.py -q
```
