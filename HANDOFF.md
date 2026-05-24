# admissions_v2 handoff

## Current Product Shape

This project now has three separate surfaces:

1. Owner/admin workspace at `#/`
   - Upload or fetch admissions materials.
   - Run the existing extraction flow.
   - Review extracted content.
   - Confirm records into the main database.
   - Search confirmed records and export Excel.

2. Private-school service center at `#/settings`
   - Open access for a partner school.
   - Copy the limited-access handoff text.
   - View submitted materials and processing progress.
   - Start owner-controlled processing for submitted PDFs or links.

3. Student/parent frontend at `#/student`
   - Collect profile information first.
   - Show schools worth checking.
   - Explain application requirements in user-facing language.
   - Accept consultation bookings.

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
- `/public/*` is for student-facing reads and bookings.

## Important Frontend Areas

- `frontend/src/App.tsx` keeps the three app shells separate by hash route.
- `frontend/src/pages/SettingsPage.tsx` is the private-school service center.
- `frontend/src/pages/StudentApp.tsx` is the student/parent frontend.
- `frontend/src/index.css` contains the iOS-like grouped layout and shared Song-style typography for settings and student surfaces.

## Current Verification Commands

```powershell
python -m pytest -q
cd frontend
npm run build
```

## Next Best Work

1. Add a clearer owner submission detail page or direct review handoff from `#/settings`.
2. Add lightweight owner/admin access protection before exposing the app outside the local machine.
3. Improve student recommendations using more confirmed data.
4. Keep UI copy non-technical for private-school and student-facing pages.
5. Keep extraction improvements narrow and evidence-based.

## Do Not Do Without Asking

- Do not rewrite the whole extraction pipeline.
- Do not split the database into a large new schema migration unless the owner approves.
- Do not expose internal review details or full exports to private schools.
- Do not add倍率数据 in v1.
