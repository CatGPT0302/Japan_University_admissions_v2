# Extraction Contract

Each JSON has exactly `document` and `records` at the top level.

`document` has exactly four nonempty strings: `university`, `year` (four digits), `source_url` (public HTTPS provenance URL), `sha256` (actual local PDF digest). If public provenance is unknown, ask for it or report that packaging is blocked; never invent an official URL.

`records` is a nonempty list. Choose one record per independently selectable program/track and admission route. Shared table cells apply to each covered row, not just the first row. Do not split courses that are assigned only after enrollment into separate application choices.

Required nonempty text fields:

```text
university admission_year faculty department
application_period deadline_rule eju_session
eju_japanese eju_general eju_math eju_physics eju_chemistry eju_biology
english_requirement
```

Also capture when available:

```text
admission_period screening_method screening_schedule result_date enrollment_period
prefecture campus required_documents eligibility evidence
```

`admission_period` follows the application's existing slot for the named admission route in these packages; do not silently infer an April/September intake from this name. `evidence` is a short provenance/review note, not reasoning or implementation notes. No confidence numbers or reviewed/confirmed flags are accepted in the input.

Every required field needs `field_evidence[field]` with exactly `page` (physical PDF integer, 1-based) and `text` (short source excerpt or clearly identifiable source summary). Evidence for additional fields uses the same shape. For multi-page conditions, choose the principal page and name all additional pages in text; do not silently drop the second reference.

Use `warnings` as a list of concrete unresolved questions with relevant pages. Do not use a bare "要確認" as the value: say what is unknown and where to check. For fields absent in the source, explicitly say "原文未記載" and cite the reviewed relevant section, making clear that it is an absence finding, not a quotation proving a negative.

Preserve complete EJU combinations in the relevant subject fields, for example:

```json
{
  "eju_physics": "必須。加えて化学・生物から1科目",
  "eju_chemistry": "選択：物理必須に加え化学・生物から1科目",
  "eju_biology": "選択：物理必須に加え化学・生物から1科目",
  "eju_math": "必須：コース2、120/200点以上"
}
```

This is only a field-shape illustration, not actual admissions advice or a complete importable record. Never reuse its numbers for another PDF. Keep general eligibility and document checklists conditional; do not claim a summary determines a person's eligibility.
