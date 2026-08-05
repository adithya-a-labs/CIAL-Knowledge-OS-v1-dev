# 007 — Add reversible Document Workspace overlays

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: MEDIUM
- **Category**: Missed opportunity, interruptibility
- **Estimated scope**: 2–4 files

## Problem

`frontend/src/pages/DocumentWorkspacePage.tsx:327-328` and `431-432` conditionally mount Corpus Tree, Document Assistant, and their backdrops in one frame. The ownership and cleanup behavior is correct but has no spatial continuity.

## Target

Retain compact overlay shells through exit and animate only opacity and edge translation using shared panel tokens. Corpus Tree enters from the left; Document Assistant from the right. Backdrops coordinate with panel timing. Rapid reversal continues from current visual state. Reduced motion removes translation. Persistent desktop panels must not animate on resize or breakpoint ownership changes.

## Steps

1. Add presence state for compact overlays only.
2. Apply side-specific transition classes/data states and coordinated backdrop opacity.
3. Preserve focus, Escape, outside click, single-overlay ownership, rotation, and breakpoint cleanup.
4. Extend mobile/touch lifecycle regressions for reversal and stale-node cleanup.

## Boundaries

- Do not change panel widths, persistence, document APIs, or desktop resize behavior.
- No bounce, blur-heavy effect, or focus-trap duplication.

## Verification

- iPad portrait/landscape and 390×844 Playwright open/close/reverse both panels.
- After every dismissal/rotation: no stale panel, backdrop, scroll lock, inert node, or focus leak.
