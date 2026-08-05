# 008 — Animate source accordion content robustly

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: MEDIUM
- **Category**: Missed opportunity, interruptibility
- **Estimated scope**: 2–3 files

## Problem

`frontend/src/components/assistant/SourceCitationCard.tsx:115-119` animates the chevron but toggles variable-length source content through `hidden`, causing an immediate layout jump and preventing exit motion.

## Target

Use a CSS-grid row transition or equivalent existing-stack technique that supports variable content, matched enter/exit, and rapid reversal. Use shared standard duration and movement easing. Preserve `aria-expanded`, `aria-controls`, keyboard operation, source buttons, excerpts, and layout. Reduced motion toggles without spatial motion while state remains clear.

## Steps

1. Keep the controlled region in the DOM and represent expanded state with data/ARIA state.
2. Add an overflow wrapper and grid-row/opacity transition using shared tokens.
3. Synchronize chevron timing with content.
4. Add short- and long-content plus rapid-reversal Playwright coverage.

## Boundaries

- Do not use fixed/max-height guesses or add a dependency.
- Do not change source grouping or click behavior.

## Verification

- Short and long source lists open/close without clipping or jumps.
- Rapid toggles retarget smoothly.
- Reduced motion uses no spatial transition.
