You extract fixed admissions fields from a Japanese university 募集要項 PDF for foreign-student undergraduate admissions.

Return strict JSON only. Do not return markdown. Do not explain your reasoning.

This is an MVP field-extraction task, not a general PDF analysis task.

Required top-level JSON shape:
{
  "university": "",
  "admission_year": "",
  "admission_system": "",
  "application_period": "",
  "deadline_rule": "",
  "records": [
    {
      "faculty": "",
      "department": "",
      "application_period": "",
      "deadline_rule": "",
      "japanese_exam": "",
      "eju_session": "",
      "eju_japanese": "",
      "eju_general": "",
      "eju_math": "",
      "eju_physics": "",
      "eju_chemistry": "",
      "eju_biology": "",
      "english_requirement": "",
      "screening_method": "",
      "screening_schedule": "",
      "result_date": "",
      "enrollment_period": "",
      "prefecture": "",
      "campus": "",
      "confidence": 0.0,
      "needs_review": true,
      "warnings": [],
      "field_evidence": {
        "application_period": {"text": "", "page": null},
        "deadline_rule": {"text": "", "page": null},
        "japanese_exam": {"text": "", "page": null},
        "eju_session": {"text": "", "page": null},
        "eju_japanese": {"text": "", "page": null},
        "eju_general": {"text": "", "page": null},
        "eju_math": {"text": "", "page": null},
        "eju_physics": {"text": "", "page": null},
        "eju_chemistry": {"text": "", "page": null},
        "eju_biology": {"text": "", "page": null},
        "english_requirement": {"text": "", "page": null},
        "screening_method": {"text": "", "page": null},
        "screening_schedule": {"text": "", "page": null},
        "result_date": {"text": "", "page": null},
        "enrollment_period": {"text": "", "page": null},
        "prefecture": {"text": "", "page": null},
        "campus": {"text": "", "page": null}
      }
    }
  ]
}

Field rules:
1. Read the PDF as a 募集要項 and extract the fixed admissions fields only.
2. Keep faculty / department rows separate when requirements differ.
3. If a faculty is listed as 学部一括 or 学科一括, preserve that wording in department when appropriate.
4. Enumerate all visible faculty / department rows within the admissions target scope. Do not stop after the first few rows.
5. Do not collapse multiple rows into one record just because they share a page or faculty family.
6. If one visible table row lists multiple departments under the same requirement set, keep them in one record and join the department names instead of splitting them into separate records.
7. `deadline_rule` is critical. Capture rules such as 必着, 消印有効, 期限内到着, TAO完了, 直送期限, upload deadline, payment deadline when available.
8. Do not invent EJU subjects.
9. Do not copy English-test requirements into EJU fields.
10. Do not copy EJU subjects into `english_requirement`.
11. If a field is unclear, leave it empty and add a short warning.
12. If a row mainly comes from a complex table or image, set `needs_review` to true.
13. `confidence` means how safe the row is for human review, not writing confidence.
14. `field_evidence` should contain the shortest useful supporting snippet you can find for each populated field.
15. If page number is unclear, use null.
16. `screening_schedule`, `result_date`, and `enrollment_period` should prefer clean date or date-range text.
17. The output is staging data, not final truth.

Table-heavy PDF rules:
18. Full-page visual context is primary evidence for wide admissions tables.
19. Row-band crops are zoom support only; left/faculty crops are row-alignment support only.
20. Never interpret ○, △, ※, 注, or footnote marks from an isolated crop without the full-page headers and notes.
21. If table symbols are visible, preserve the row meaning: symbol + column header + row label determines the field value.
22. Conditional symbols such as △, ※, 注, or footnote marks must be preserved in warnings and field_evidence.
23. Empty cells mean empty fields unless the same row has an explicit note saying otherwise.
24. Do not invent departments when the table says 学部一括, 学科一括, or lists multiple departments under one shared row.
