# AGENTS.md

## Project Role

This repository is an LLM-assisted information extraction and validation system for Japanese university international admissions PDFs.

The current UI task is **visual polish only**. Treat the frontend as an internal SaaS dashboard for admission-data reviewers.

## Hard Boundaries

Do not change backend extraction logic.
Do not change database schema.
Do not change API contracts.
Do not expand the PDF sample set.
Do not rewrite the pipeline.
Do not delete `trace_debug.json`.
Do not remove existing FastAPI / Streamlit / React demo structure.

When working on UI, restrict changes to:

- `frontend/`
- UI-related docs under `docs/`
- optional progress notes such as `progress.md`

## UI Quality Target

Make the app feel like a polished professional dashboard, not a raw engineering demo.

Preferred direction:

- clean internal SaaS dashboard
- bento-style information hierarchy
- soft enterprise UI
- generous spacing
- clear typography scale
- calm colors with strong risk-state contrast
- Chinese interface copy
- visual emphasis on review workflow and risk prioritization

The app should still look serious enough for a leader demo.

## Frontend Constraints

Current frontend stack:

- React
- TypeScript
- Vite
- Tailwind is available, but existing pages may use inline styles
- Keep dependencies minimal unless there is a clear reason

Before adding new packages, prefer improving existing CSS, layout, spacing, component hierarchy, and copy.

## UI Polish Checklist

When improving `frontend/`, check the following:

1. Layout
   - Clear sidebar and main work area
   - Good max-widths and readable content density
   - Responsive behavior for narrower screens where practical

2. Navigation
   - Current step should be obvious
   - Page labels should be human-readable
   - Workflow order should feel natural: run -> review -> records

3. Review workflow
   - High-risk records must visually stand out
   - Medium-risk and low-risk should be distinct but less alarming
   - The user should immediately know what to do next
   - Bulk low-risk review should look useful but not dangerous
   - Confirm-to-database action should feel final and cautious

4. Data fields
   - Critical fields need stronger visual cues
   - Evidence snippets should be easy to open and read
   - Modified fields should be visibly marked
   - Empty values should have graceful presentation

5. States
   - Loading states
   - Empty states
   - Error states
   - Success messages
   - Backend disconnected state

6. Visual system
   - Consistent radius, borders, shadows, padding, font sizes
   - Avoid random one-off colors
   - Use risk colors consistently
   - Make buttons feel tactile but not flashy

7. Copywriting
   - Use natural Chinese UI text
   - Avoid overly technical wording where a reviewer-facing phrase is clearer
   - Keep labels short
   - Put longer guidance in helper text or cards

## Suggested Visual Language

Use a warm neutral dashboard base with restrained accents:

- background: warm off-white / stone
- surface: white
- text: dark slate / near-black
- border: soft stone / gray
- primary action: dark slate or deep blue
- success: green
- warning: amber
- danger: red

Do not make it look like a toy app. Avoid rainbow gradients unless used very lightly.

## Recommended Task Prompt for Codex

Use this when starting a UI-focused Codex session:

```text
Polish the React frontend into a more professional internal SaaS dashboard.

Scope:
- Work only inside frontend/ unless documentation updates are needed.
- Do not touch backend extraction logic, database schema, API contracts, or sample data.
- Keep the Chinese UI.
- Make the review workflow visually clearer and more polished.
- Improve layout, spacing, typography, cards, buttons, badges, empty/loading/error states, and risk hierarchy.
- Keep changes incremental and reviewable.
- After changes, run the frontend build if possible.
- Update progress.md with what changed and what remains.
```

## Completion Standard

A good UI polish PR should include:

- Clear before/after summary
- List of modified frontend files
- Confirmation that backend logic was untouched
- Build/test result or honest note if not run
- Remaining UI follow-ups
