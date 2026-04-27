# Current Handoff

## Project Positioning
This project is an LLM-assisted information extraction and validation system for Japanese university admission guideline PDFs, especially 留学生募集要項.

The goal is not to build a PDF OCR/vision engine from scratch. Instead, the system uses LLM/Agent-based reading to extract key admission information from PDFs and structure it into human-verifiable CSV/JSON/table fields.

## Current Status
- First version of trace_debug.json has been generated.
- The overall direction is validated.
- The main bottleneck is snippet quality.
- We should not expand the sample size yet.
- The next step is to improve snippet quality only.

## Current Priority
Focus only on snippet improvement:

1. Improve context window selection.
2. Improve field-to-snippet matching.
3. Improve snippet readability for human validation.
4. Make sure each extracted field can be traced back to a useful source snippet.
5. Avoid over-expanding context so that snippets remain concise and reviewable.

## Do Not Do Yet
- Do not expand the sample set.
- Do not redesign the entire pipeline.
- Do not over-optimize UI yet.
- Do not rewrite the whole project structure unless necessary.
- Do not treat this as a pure OCR or PDF vision project.

## Later Phases
- UI Phase2
- Leader demo
- README polishing
- More stable output comparison
- Human validation workflow

## Repository Structure Guidance (Safe, Non-Breaking)
Target shape for gradual cleanup:

```text
project-root/
├─ data/
│  ├─ samples/
│  ├─ traces/
│  └─ outputs/
├─ src/
│  ├─ extract/
│  ├─ snippet/
│  ├─ schema/
│  └─ ui/
├─ docs/
│  ├─ handoff.md
│  ├─ leader_demo.md
│  └─ phase2_ui.md
├─ README.md
└─ TODO.md
```

Current policy:
- Keep existing runtime paths (`scripts/`, `input_pdfs/`, `output_pages/`, `database/`) intact.
- Do not move working pipeline files in this stage.
- Use docs + lightweight directory scaffolding first, then migrate only when needed with compatibility shims.
