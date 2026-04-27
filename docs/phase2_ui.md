# UI Phase2 Draft

## Purpose
The UI Phase2 should help humans verify extracted admission information quickly.

## Core User Flow
1. Upload or select a PDF.
2. Run extraction.
3. Show structured fields.
4. Show source snippet beside each field.
5. Allow user to confirm, edit, or flag uncertain fields.
6. Export validated CSV/JSON.

## Important Design Principle
The UI should not only show extracted values. It must show why the system extracted them.

Each field should ideally include:
- field name
- extracted value
- confidence / status
- source snippet
- page number if available
- validation action

## Priority
The first UI version should prioritize validation efficiency, not visual beauty.

## Scope Boundaries for Phase2
- Keep existing backend contracts where possible.
- Do not treat UI Phase2 as extraction model redesign.
- Prefer smaller, review-oriented interactions over dashboard complexity.
