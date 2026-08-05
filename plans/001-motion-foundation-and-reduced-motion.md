# 001 — Establish the CIAL motion foundation and reduced-motion policy

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: MEDIUM
- **Category**: Accessibility, cohesion, tokens
- **Estimated scope**: 2–4 files

## Problem

`frontend/src/index.css:446-518`, `821-831`, and `951-963` mix 150/180/220ms values and weak built-in curves without shared motion tokens. `frontend/src/index.css:860-872` globally clamps every animation and transition to `0.001ms`, removing useful color, focus, selected, and state feedback while failing to govern JavaScript smooth scrolling.

## Target

Add a minimal semantic vocabulary to `frontend/src/index.css`:

```css
--motion-duration-press: 140ms;
--motion-duration-short: 160ms;
--motion-duration-standard: 180ms;
--motion-duration-panel: 220ms;
--motion-ease-enter: cubic-bezier(0.23, 1, 0.32, 1);
--motion-ease-move: cubic-bezier(0.77, 0, 0.175, 1);
--motion-ease-drawer: cubic-bezier(0.32, 0.72, 0, 1);
```

Under `prefers-reduced-motion: reduce`, remove smooth scrolling, translation, pulsing, and nonessential keyframes while keeping short opacity/color/focus/state transitions. Do not use a universal duration clamp.

## Repo conventions to follow

- Semantic tokens already live in `frontend/src/index.css`.
- Preserve the intentional `frontend/src/index.css:19` note-citation outline fallback.
- Preserve all colors, spacing, typography, and theme behavior.

## Steps

1. Add the six motion tokens alongside the existing semantic variables.
2. Replace active audited literal durations/curves with those tokens.
3. Replace the universal reduced-motion clamp with targeted utility/component behavior.
4. Add a small frontend hook for JavaScript `prefers-reduced-motion` checks if needed by multiple components.
5. Update motion documentation and regression tests.

## Boundaries

- Do not add dependencies or change application architecture.
- Do not use `transition-all`, `ease-in`, `scale(0)`, bounce, or spring motion.
- Do not remove focus, color, selected, or state feedback.

## Verification

- `rg -n "transition-all|0\.001ms|ease-in|scale\(0" frontend/src`
- Run reduced-motion Playwright checks and confirm no spatial translation or smooth JS scrolling.
- Run `pnpm.cmd run typecheck`, `pnpm.cmd test`, and production build.
- Done when tokens are the only active scoped duration/easing source and reduced motion remains understandable.
