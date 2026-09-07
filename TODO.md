# TODO

## Completed foundation

- [x] Isolated local demo with direct Codex reading, no additional model calls.
- [x] Authenticated extraction package + PDF submission to the configured draft DB.
- [x] Source hash/page validation, atomic document writes and exact-retry receipts.
- [x] Preserve existing drafts/human edits; never confirm records during ingestion.
- [x] Standalone submission helper in the shareable skill package.
- [x] Review deep link survives login; browser review/export regression passes.
- [x] Record repository privacy and workspace cleanup rules in AGENTS.md.

## Current acceptance: seven universities

- [x] Locate official 2027 admissions source entrypoints for MARCH, Waseda and Keio.
- [ ] Resolve all source PDFs, including Rikkyo's official-linked viewers and errata.
- [ ] Inventory all in-scope faculties/departments/routes and document exclusions.
- [ ] Codex reads every source and extracts conditions with physical-page evidence.
- [ ] Import drafts, verify completeness and independently check high-impact fields.
- [ ] A human reviews and publishes actual admissions records.

Source discovery is not extraction completion. Current seven-school draft count
is 14: Keio main 11 + medicine 1; Rikkyo intercultural written/interview 1 +
document screening 1. None is human-confirmed. Seven other acquired PDFs remain
unread; Waseda's direct PDF download returns HTTP 403. The 12 older Fukui/KIT
records are separate regression data. Local final outputs are under
runtime/acceptance_2027/; PDF sources stay under data/uploads/acceptance_2027/.
The readable report now distinguishes selection routes in both overview and detail.

## Next product work

- [ ] Versioned schema: separate selection route/intake, requirements_note, multi-page evidence.
- [ ] Immutable publication snapshots; draft edits must not affect public evidence.
- [ ] Minimal pending/published maintenance lists and shared detail preview.
- [ ] Student search, readable timeline/requirements and 2-4 program comparison.
- [ ] Mobile/desktop usability checks with restrained Liquid Glass styling.
- [ ] Real user task trial and documented feedback, without fabricated outcomes.
- [ ] Audit dependencies, authentication, file access and backup recovery before hosting.

## Later

- Historical competition and score data with explicit statistical definitions.
- Eligibility-aware shortlist; no unsupported acceptance probabilities.
- No billing, CRM, bookings, tenant expansion or eligibility guarantees in this MVP.

See docs/PROJECT_ROADMAP.md and docs/AI_INGESTION.md. Keep the repository private,
retain source evidence, and remove only task-owned disposable intermediates.
