# Leader Demo Draft

## Demo Positioning
This project is not just a script that reads PDFs. It is a workflow system that turns Japanese university admission PDFs into structured, human-checkable data.

## Problem
Japanese university admission guidelines are long, inconsistent, and difficult to manually convert into structured tables. Important fields such as application period, EJU requirements, English test requirements, selection method, and deadlines are scattered across different pages and formats.

## Solution
The system uses LLM-assisted extraction to read PDF content, identify key admission fields, and output structured data with traceable snippets for human verification.

## Current Demo Scope
The current demo should focus on:
- showing one or a few sample PDFs
- showing extracted structured fields
- showing trace_debug.json
- explaining that the current bottleneck is snippet quality
- showing that the next development step is improving snippet traceability

## Key Message
The project has already passed the first technical feasibility check. The next stage is not about adding more samples, but about improving the reliability and reviewability of extracted evidence.

## Suggested Demo Narrative
1. Show raw PDF complexity (multi-page, mixed formats).
2. Show extracted structured fields in staging/records.
3. Show trace sidecar evidence for `application_period`.
4. Call out current limitation: snippet quality.
5. Explain near-term plan: tighter field-to-snippet traceability, then UI Phase2 validation flow.
