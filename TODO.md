# TODO

## Now

- Stabilize the partner service center as the first usable cooperation flow.
- Keep owner/admin, partner service center, and student frontend visually and semantically separate.
- Keep `/public/*` and `/v1/*` reading confirmed admissions data only.
- Keep partner submissions owner-controlled: submitted material enters a queue, extraction can be started by owner/admin, and final confirmation stays in the admin review flow.
- Remove user-facing engineering wording from the frontend.

## Next

- Add an owner-facing submission detail view with clearer links into the review page.
- Add lightweight access protection before any external deployment of the owner/admin workspace.
- Improve student result ranking with more real confirmed records.
- Add a student-side booking smoke check against a confirmed admissions record.
- Keep extraction quality improvements focused on known gaps; do not rewrite the pipeline.

## Later

- Add organization-level reporting and usage summaries.
- Add more universities only after the core review and confirmation loop is stable.
- Add email/calendar/payment integrations only after booking v1 is proven.
- Consider larger data model migrations only after the projection layer becomes a bottleneck.

## Out Of Scope For v1

-倍率数据
- Full SaaS tenant management
- Partner self-confirmation into the master database
- Full database export for partner users
- Rebuilding the extraction workflow as a separate packaged tool
