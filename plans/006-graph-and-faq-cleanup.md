# 006 — Remove broad and decorative hover motion

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: MEDIUM
- **Category**: Performance, purpose
- **Estimated scope**: 3–5 files

## Problem

`frontend/src/pages/KnowledgeGraphPage.tsx:113-119` uses `transition-all` while changing SVG radius, stroke, stroke width, and filter. `frontend/src/pages/FAQsPage.tsx:120-153` lifts a non-interactive article and uses broad transitions. Additional audited `transition-all` occurrences remain across scoped cards and progress indicators.

## Target

Use targeted properties only. Knowledge Graph hover/selection must remain restrained and responsive without transitioning paint-heavy attributes together. FAQ question articles remain stationary; feedback lives on the actionable “View Answer” button. Replace every audited scoped `transition-all` with exact property lists or remove it when no transition is useful.

## Steps

1. Refactor graph hover/selection to lightweight targeted feedback.
2. Remove FAQ article lift and broad transition; add scoped action feedback.
3. Replace all remaining audited `transition-all` utilities with exact lists.
4. Gate any retained hover displacement behind fine-pointer media if applicable.
5. Add source-contract tests ensuring banned patterns do not return.

## Boundaries

- Do not redesign graph data, layout, colors, FAQ hierarchy, or actions.

## Verification

- Repeated Playwright graph hover must remain responsive with no `transition-property: all`.
- FAQ mobile/desktop interaction and keyboard focus remain clear.
- `rg -n "transition-all"` returns no audited application-source occurrence.
