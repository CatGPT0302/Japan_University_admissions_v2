```
You are continuing an existing GitHub project.

Repository:
CatGPT0302/Japan_University_admissions_v2

Branch:
codex-frontend

Before doing anything, read:

* README.md
* HANDOFF.md
* docs/AGENT_BOOTSTRAP.md
* docs/handoff.md
* TODO.md
* trace_debug.json

Project summary:
This is an LLM-assisted extraction and validation system for Japanese university international admissions PDF data. It converts long and inconsistent admission guideline PDFs into structured, human-verifiable fields.

Important:
This is not a pure OCR project.
Do not rebuild the whole pipeline.
Do not expand the sample set.
Do not over-design UI yet.

Current validated conclusion:
The overall technical direction works, but snippet quality is insufficient.

Your task:
Focus only on snippet quality.

Please:

1. Inspect trace_debug.json.
2. Identify weak snippets.
3. Improve field-to-snippet matching and context window selection.
4. Keep sample size fixed.
5. Preserve existing backend/frontend demo structure.
6. Create or update docs/snippet_quality_report.md explaining:

   * what was wrong
   * what changed
   * before/after examples
   * remaining risks

Do not make unrelated changes.
Commit with a clear message:
fix: improve snippet traceability
```
