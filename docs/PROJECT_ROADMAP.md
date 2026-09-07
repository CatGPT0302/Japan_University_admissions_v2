# Admissions information platform

## Product

Official admissions PDF -> multimodal extraction -> authenticated draft import ->
human review and publication -> student search, readable requirements and comparison.

The first release runs locally. Keep Python/FastAPI, React and SQLite. Do not call
an external model API when Codex is reading source PDFs. Uncertainty is explicit;
structural validation is not factual verification. Never publish automatically.

## Delivery order

1. Provider-neutral ingestion with source hashes, evidence, idempotence and atomic
   document writes. Preserve human edits on retries and re-extraction.
2. Pending/published lists and shared detail preview with evidence, edits and human
   publication. Published snapshots must not join mutable draft evidence.
3. Student search, readable details, source-page navigation and 2-4 program comparison.
   Use restrained Liquid Glass navigation with legible information surfaces.
4. Small user trial, permission/security and backup/restore checks before deployment.
5. Historical statistics and score comparison only with documented source and scope.
   Never confuse application thresholds with successful applicant scores.

## Seven-university acceptance scope

Default: 2027 undergraduate international-student admission routes at Meiji,
Aoyama Gakuin, Rikkyo, Chuo, Hosei, Waseda and Keio. Inventory every faculty,
department and route before claiming completion. Graduate, transfer and separate
English-medium programs are outside the initial scope unless explicitly added.
Unavailable 2027 sources stay unavailable; do not replace them with another year.

Check eligibility, application and postal deadlines, EJU subject combinations,
valid sittings, English tests, documents, selection, results and enrollment dates.
Every important value needs official provenance and physical PDF page evidence.
Check errata and supplements. Existing Fukui/KIT examples remain regression data.

## Workspace and repository hygiene

Keep downloaded source PDFs under ignored data/uploads/ and durable local results
under runtime/. Keep this task's disposable intermediates in runtime/work/ only.
Remove only intermediates created by this task after validation; preserve source
evidence, databases and user files. Do not create scattered desktop/temp artifacts.
Do not commit credentials, databases, PDFs, rendered pages, exports or dependencies.
Verify GitHub remains private before every push. Audit staged files and report
tests, pending acceptance work and the pushed commit without claiming completion
for unread documents or unreviewed records.
