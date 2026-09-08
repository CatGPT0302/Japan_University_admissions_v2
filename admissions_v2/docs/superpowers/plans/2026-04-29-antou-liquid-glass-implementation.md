# 案头 Liquid Glass UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the `frontend/` UI into the `案头` branded Liquid Glass workspace while keeping backend logic, database schema, API contract, and sample data unchanged.

**Architecture:** Keep the existing React page structure, but refit the app shell, page copy, and component hierarchy around a single left-rail workspace model. Reuse the current API client and page responsibilities while replacing technical copy and sharpening the list-to-detail workflow on all three main screens.

**Tech Stack:** React 18, TypeScript, Vite, CSS in `frontend/src/index.css`

---

### Task 1: Rebrand the app shell and navigation

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/index.css`

- [ ] Replace the current product name with `案头` and keep the sidebar as the only first-level navigation container.
- [ ] Remove explanatory or technical-facing copy from the shell header and sidebar cards.
- [ ] Tighten the shell styling toward a softer full-page glass treatment with subtler borders, lighter shadows, and calmer navigation emphasis.
- [ ] Run `npm run build` from `frontend/` and confirm the shell compiles with the renamed branding.

### Task 2: Refine the Run page into a glass workspace intake panel

**Files:**
- Modify: `frontend/src/pages/RunPage.tsx`
- Modify: `frontend/src/index.css`

- [ ] Keep all intake controls in the left rail and reduce the right pane to upload, candidate, and result surfaces only.
- [ ] Remove any design-explainer or system-explainer copy and replace it with concise product copy.
- [ ] Make candidate selection and result states feel like a polished workspace rather than an operator dashboard.
- [ ] Run `npm run build` from `frontend/` and confirm the page compiles after the content and layout updates.

### Task 3: Refine the Review page into a two-level queue workspace

**Files:**
- Modify: `frontend/src/pages/ReviewPage.tsx`
- Modify: `frontend/src/components/DashboardCharts.tsx`
- Modify: `frontend/src/index.css`

- [ ] Keep documents and filters in the left rail, records in the main queue, and record editing in a dedicated second-level detail surface.
- [ ] Remove technical or process-explainer language and keep the copy task-focused.
- [ ] Soften risk visualization and chart styling so they support the workflow without dominating it.
- [ ] Run `npm run build` from `frontend/` and confirm the page compiles after the queue and detail updates.

### Task 4: Refine the Records page into a product-style archive browser

**Files:**
- Modify: `frontend/src/pages/RecordsPage.tsx`
- Modify: `frontend/src/index.css`

- [ ] Keep filters and export in the left rail and present records as left-click entry points into a second-level archive detail view.
- [ ] Remove any lingering technical or dev-facing text from record list and detail states.
- [ ] Align the cards, detail fields, and supporting chart with the same Liquid Glass system used elsewhere.
- [ ] Run `npm run build` from `frontend/` and confirm the archive page compiles after the visual cleanup.

### Task 5: Final visual and wording sweep

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/RunPage.tsx`
- Modify: `frontend/src/pages/ReviewPage.tsx`
- Modify: `frontend/src/pages/RecordsPage.tsx`
- Modify: `frontend/src/components/DashboardCharts.tsx`
- Modify: `frontend/src/index.css`

- [ ] Check that the UI no longer exposes `admissions_v2` as the primary product name.
- [ ] Check that no page contains prompt-like, AI-like, or design-explainer wording.
- [ ] Check that all row-level entities still open into second-level detail views by left click.
- [ ] Run `npm run build` from `frontend/` and use the successful build as the completion gate.
