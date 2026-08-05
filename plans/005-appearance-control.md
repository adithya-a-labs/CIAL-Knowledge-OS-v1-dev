# 005 — Synchronize Appearance control motion

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: MEDIUM
- **Category**: Easing, duration, cohesion
- **Estimated scope**: 2–3 files

## Problem

`frontend/src/index.css:446-518` mixes 150, 180, and 220ms transitions. The thumb uses an entrance-like curve even though it moves on screen, exceeding the documented 140–180ms theme-control budget.

## Target

Use `--motion-duration-standard` (180ms) for thumb, geometry, icons, and labels. Thumb transform uses `--motion-ease-move`; color/background use a restrained standard UI curve/token. Preserve Light/System/Dark behavior, keyboard roving focus, ARIA, persistence, collapsed/mobile forms, and the 270px container query.

## Steps

1. Replace mixed appearance timings with shared tokens.
2. Verify horizontal and vertical thumb transforms remain correct.
3. Extend existing appearance verifier assertions for synchronized computed durations and reduced motion.

## Boundaries

- No theme, color, markup, geometry, or keyboard-model redesign.

## Verification

- Run `node scripts/verify_appearance_toggle.mjs` against the validation app.
- Verify 180ms synchronized computed timing in expanded, collapsed, and mobile forms.
