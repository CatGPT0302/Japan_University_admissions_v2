# Agent Bootstrap

## Read First
Before making any changes, read these files in order:

1. README.md
2. HANDOFF.md
3. docs/handoff.md
4. TODO.md
5. trace_debug.json
6. docs/phase2_ui.md
7. docs/leader_demo.md

## Project Positioning
This is an LLM-assisted information extraction and validation system for Japanese university international admissions PDF data.

It is not a pure OCR project.
It is not trying to build PDF vision recognition from scratch.
It uses LLM/Agent-based reading to extract structured admission information from PDFs and make the results human-verifiable.

## Current Stage
The first feasibility pass has succeeded.

Current conclusion:
- The overall direction is valid.
- trace_debug.json has been generated.
- The main bottleneck is snippet quality.
- The next stage should focus on snippet quality and traceability.
- Do not expand the sample set yet.

## Current Priority
Focus on:
- snippet quality
- field-to-snippet matching
- context window selection
- human verification readability
- making every extracted value traceable to a useful source snippet

## Do Not Do
Do not:
- expand samples
- redesign the entire pipeline
- rewrite the whole project
- convert this into an OCR project
- over-optimize UI before snippet quality is fixed
- move files aggressively if that risks breaking existing scripts
- delete trace_debug.json
- remove existing demo frontend/backend structure

## Recommended Next Task
The next agent should start with:

1. Inspect trace_debug.json.
2. Identify low-quality snippets.
3. Improve snippet generation logic only.
4. Re-run the same sample.
5. Compare before/after trace quality.
6. Document findings in docs/snippet_quality_report.md.

## Success Criteria
A successful next step means:
- snippets are more useful for human validation
- each extracted field has clearer evidence
- context is concise but sufficient
- no sample expansion occurred
- existing demo still runs
