# Quality acceptance checkpoint

## Scope and verdict

Waseda is excluded at the user's request; no further acquisition retries.
The current sample contains four PDFs and 14 unreviewed records: Keio main 11,
Keio medicine 1, Rikkyo intercultural written/interview 1 and document selection 1.
This is a sample quality check, not complete six-university coverage or approval
to publish. Seven acquired PDFs still need reading. No records were confirmed.

## Data checks

- Local PDF hashes, required fields and physical-page bounds pass validation.
- All 14 records and their field evidence match the imported staging data.
- No duplicate program/route identities were found across the four packages.
- Rechecked Keio's EJU matrix (main PDF page 22), medicine's science selection
  and valid sittings (page 20), and Rikkyo's route-specific language thresholds
  (G001 page 5 and H page 6). No conflict found in these sampled conditions.
- The sample does not certify every fact, all exceptions or later university
  corrections. Human review and full route coverage remain outstanding.

## Functional issues fixed

1. Public source metadata and quality previously joined mutable draft/source
   tables. Confirmation now copies evidence, risk and source filename alongside
   the already-copied fields and URL in the same transaction. Public queries read
   the confirmed record, not later edits to the draft or source metadata.
2. Editing a field previously replaced its original quotation with the edited
   value. Original evidence is now preserved unless evidence is explicitly edited.
   A corrected value must not masquerade as a PDF quotation.

The migration only adds columns. Existing confirmed records retain their stored
values and URL; missing historic evidence is not reconstructed from today's
drafts. Source content storage, explicit republication/version history, and a
consumer-facing evidence view still require their own work.

## Verification

- Full suite: 295 passed, 3 skipped; one existing dependency deprecation warning.
- Backend compilation and the demo frontend build passed.
- Single-record and batch confirmation snapshots, repeated initialization,
  source/draft edits, explicit evidence corrections and the review gate are tested.
- Live local API: 14 target drafts remain unreviewed; public records remain zero.
- Demo database backed up before applying the additive migration. PostgreSQL SQL
  follows existing migration helpers but was not exercised against a live server.

## Repeat the read-only data audit

```bash
python -m scripts.audit_acceptance \
  --manifest data/acceptance_sources_2027.json \
  --pdfs data/uploads/acceptance_2027 \
  --extractions runtime/acceptance_2027/extractions \
  --database runtime/local_demo/data/admissions.db
```

The command checks structure, coverage and package/database drift. Legitimate
human edits are reported for inspection, never overwritten. It cannot certify
admissions facts and has no publication action. The local machine-readable
checkpoint is runtime/acceptance_2027/quality_audit.json.

## Maintenance UI checkpoint

The default owner screen is now review, with two primary entries: pending review
and published records. Upload, export and quality remain available under More
Tools. Publishing returns to records and keeps that route after refresh. Review
handoffs preserve the document ID, and published details include the route name.
Unsaved changes, outstanding reviews and in-flight saves block publication.
Saving an edited unpublished draft without reviewing it resets its review flag.

Verification: TypeScript/Vite build passed; the 295-test Python suite passed with
3 skips. The dedicated maintenance-smoke.mjs passed at 1440px and 390px using
intercepted API fixtures, including publication guards and refresh. Screenshots
were inspected; a real local draft and PDF preview were also opened read-only.
The older multi-surface smoke script was updated for navigation labels but its
full multi-surface suite was not run in this checkpoint. Real drafts remain 14,
with zero confirmed records. Pending-only queue filtering and explicit version
republication remain unfinished.
