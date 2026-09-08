# Personal Project Demo Plan

## Goal

Build a working, explainable first-year student project: turn Japanese university
admissions PDFs into readable structured data with mandatory human review.
Use Codex to read the source material; do not require a separate model API for
the demonstration. Preserve existing product surfaces without expanding them.

## Acceptance Checklist

- [x] Start on macOS with isolated demo data; preserve the original database.
- [x] Read one existing official PDF and retain evidence for important fields.
- [x] Import the extracted data into staging without automatic confirmation.
- [x] Verify UI review/edit/confirm/query/export on a clearly synthetic fixture; real drafts remain unconfirmed.
- [x] Display EJU selection rules, deadlines, English requirements, and uncertainty.
- [x] Verify restart persistence, tests, build, and browser workflow.
- [x] Prepare a short explanation, workflow diagram, and three-minute demo script.
- [ ] Prepare tasks for 1-2 real users; collect actual feedback with consent.
- [ ] Make 1-2 changes based on that feedback and ask the users to retry.

## Evidence Rules

Keep technical verification separate from user feedback. Automated tests and
agent browser checks are not user interviews. Do not invent feedback, time
savings, or evidence of real adoption. Historical admission documents must show
their actual year and must not be presented as current application advice.

## Out Of Scope

Billing, multi-tenant expansion, large-scale infrastructure, additional university
coverage, and broad frontend redesign are not required for this demonstration.

## Verified Evidence

- Two directly read official PDFs: Fukui engineering (five records) and Kyoto Institute of Technology (seven records), with physical-page evidence, EJU selection conditions and errata/conflicts retained. See `examples/demo/` and the two `DEMO_CASE*.md` reports.
- Isolated demo database: 12 staging records, zero real confirmed records. Identical reimports do not add rows. Original database SHA-256 remained `bf3000ed12dac356a5b342e81cc767b7bff9a4f7729bb02afaf83e9c7f7a9b43` at the last data verification.
- Browser checks covered login, viewing PDF/fields, draft editing and persisted storage. Synthetic confirmation/query/download and four-width responsive checks subsequently passed.
- Synthetic API tests cover review gating, confirmation, filtered queries, parsed Excel/CSV output and preservation of EJU rules. They are not human review of real records.
- Latest full Python test run: 283 passed, 3 skipped, one dependency deprecation warning. Demo TypeScript/Vite build passed (91 modules).
- Batch helper produced JSONL, readable Markdown, CSV and a field review queue for two documents/12 drafts. The outputs are snapshots of extracted JSON, not a live view of later database edits.
- Skill archive passed format validation and ran from a separate extracted directory. Installed skill appeared in Codex's available-skill list; its installed helper also produced 12 draft records. Another user's fresh-PDF trial remains pending.
- `docs/PROJECT_DEMO.md` contains the project explanation, workflow and three-minute script. `docs/USER_TRIAL.md` remains an unfilled real-user protocol.

## Remaining Acceptance Work

1. Have 1-2 actual participants try the workflow, collect consented feedback, implement 1-2 supported improvements and retest with them.
2. Repeat relevant acceptance checks after any feedback-driven changes.

No real user feedback, accuracy rate, time-saving measurement or production-readiness claim has been established. Technical checks alone do not complete these remaining requirements.

Verification screenshots are archived under `runtime/local_demo/verification_screenshots`. Task-created PDF-render scratch directories, the standalone unpack test and redundant installed-skill test output were removed. Source PDFs, databases, readable results and the skill ZIP are retained. Changes are local and have not been committed or pushed in this work.

## Final Technical Acceptance Update

- Complete synthetic browser path passed via `scripts/verify_demo_ui.py`: edit/save, preserved source evidence, review, confirm, filtered query, real Excel/CSV download and parsed-content checks. Its test document was removed afterwards; all 12 real drafts remain unreviewed and the confirmed table is empty.
- Responsive layout checked at 390, 1024, 1440 and 1920px: page scroll width equals viewport width. Mobile filename overflow and medium-desktop fixed-column overflow were fixed and rebuilt.
- Real user trial remains unstarted. Do not substitute these browser checks for participant feedback. The next required external input is actual trial observations; feedback-driven changes cannot be chosen or claimed before that evidence exists.
