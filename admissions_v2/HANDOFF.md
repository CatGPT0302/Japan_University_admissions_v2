# admissions_v2 handoff

## Current Product Shape

This project now has three separate surfaces. In production, use separate deployments/sites for these surfaces rather than exposing them as different hash routes on one public URL.

1. Owner/admin workspace
   - Upload or fetch admissions materials.
   - Run the existing extraction flow.
   - Review extracted content.
   - Confirm records into the main database.
   - Search confirmed records and export Excel.

2. Partner service center
   - Open limited access for a partner.
   - Copy the limited-access handoff text.
   - View submitted materials and processing progress.
   - Start owner-controlled processing for submitted PDFs or links.

3. Student/parent frontend
   - Collect profile information first.
   - Show schools worth checking.
   - Explain application requirements in user-facing language.
   - Does not collect consultation bookings.

Do not merge these into one dashboard. The admin tool is the data production tool; the student frontend is the real user-facing product.

## Data Ownership Boundary

- The owner controls the extraction workflow, master database, and final confirmation.
- Private schools receive limited use rights through issued access.
- Private schools can submit materials and query allowed services, but cannot confirm data, see internal review details, or export the full master database.
- API secrets are stored as hashes. The full secret is only shown once.

## Important Backend Areas

- `scripts/api.py` exposes admin, public, licensed, settings, and owner queue routes.
- `scripts/db.py` owns SQLite/PostgreSQL-compatible persistence and the public projection helpers.
- `/admin/submissions` is the owner queue for private-school submitted materials.
- `/v1/documents/submissions` is the licensed submission endpoint for private schools.
- `/public/*` is for student-facing reads and recommendations.
- Booking endpoints may still exist for legacy compatibility, but they are not part of the active student or partner product flow.

## Important Frontend Areas

- `frontend/src/App.tsx` keeps the app shells separate by `VITE_APP_SURFACE`; combined hash routing is only for local debugging.
- `frontend/src/pages/SettingsPage.tsx` is the partner service center.
- `frontend/src/pages/StudentApp.tsx` is the student/parent frontend.
- `frontend/src/pages/ReviewPage.tsx` is the owner review workbench: source PDF preview, grouped editor, field evidence, priority hints, and confirm flow.
- `frontend/src/pages/ExportPage.tsx` is the owner export center: single-school export, batch export, saved combinations, row-level export actions, and source-review handoff.
- `frontend/src/pages/QualityPage.tsx` is owner-only quality/source monitoring: source watchlist, change queue status filters, re-extraction handoff, and correction metrics.
- `frontend/src/index.css` contains the grouped owner/partner/student visual system and shared Song-style typography.

## Current Verification Commands

```powershell
python -m pytest -q
cd frontend
npm run build
```

## Next Best Work

1. Improve source-change review reports so changed official pages/PDFs produce clearer owner-readable summaries.
2. Add more checked rows only where official source evidence is available; do not expand seeds blindly.
3. Improve student recommendations using more real confirmed records.
4. Keep private-school and student-facing copy non-technical.
5. Keep extraction improvements narrow and evidence-based.

## Do Not Do Without Asking

- Do not rewrite the whole extraction pipeline.
- Do not split the database into a large new schema migration unless the owner approves.
- Do not expose internal review details or full exports to private schools.
- Do not add 倍率数据 in v1.
