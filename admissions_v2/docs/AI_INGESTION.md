# AI extraction import

The current milestone accepts the existing evidence-backed `document` / `records`
package format and its original PDF. It does not extract by calling another model.
See the skill's `references/schema.md` for fields. No client-supplied review flags
are accepted. Every imported record remains a draft requiring human review.

## One-command local submission

With the local demo running, from the repository root:

```bash
.venv/bin/python scripts/submit_extraction.py examples/demo/fukui_2027_codex.json --source-pdf data/uploads/fukui_engineering_2027_undergrad.pdf --access-file runtime/local_demo/access.json
```

Use `--server http://127.0.0.1:PORT` when the demo uses another port.
The result includes a preview link, document ID, record count and receipt ID.
The command writes drafts into the running server's configured database, not a
separately guessed local database. It never prints credentials.

## Other AI clients

Configure `ADMISSIONS_INGEST_TOKEN` on the server and client using a high-entropy
secret. This bearer token works only for ingestion routes; it does not authorize
confirmation, publication, exports or arbitrary database access. Use HTTPS except
on loopback. Keep tokens in local environment configuration, never in shared skills.

- `POST /ingestions`: multipart `package` (JSON text) and `file` (source PDF).
- `GET /ingestions/{ingestion_id}`: authenticated receipt lookup.
- Owner session cookies are also accepted for local/manual use.
- Maximum PDF: 50 MiB; extraction JSON: at most 2 MiB (the multipart parser may
  impose a lower field limit). Source SHA, PDF signature, pages and record identity
  must validate. Official-source claims still require human verification.
- Invalid content returns 422; removed/corrupt prior sources return 409.
- Exact retries return `already_imported`; changed packages create separate drafts.
- One document is written transactionally. Failed imports roll back all its rows.
- Multipart temporary copies are removed in both success and failure cases.

## Remaining project work

This is the ingestion milestone, not completion of the whole roadmap. Seven-school
sources are inventoried in `data/acceptance_sources_2027.json`; they have not yet
passed full extraction or human review. Next: source-by-source extraction, richer
versioned fields/multi-page evidence, immutable publication snapshots, simplified
maintenance UI and student comparison. Existing public views are not yet the new
snapshot publication model. Do not call this deployment-ready.
