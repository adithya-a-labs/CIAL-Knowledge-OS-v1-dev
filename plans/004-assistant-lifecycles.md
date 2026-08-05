# 004 — Make Assistant panes and History drawer reversible

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: HIGH
- **Category**: Easing, interruptibility, missed opportunity
- **Estimated scope**: 3–5 files

## Problem

`frontend/src/components/assistant/ChatPanel.tsx:839-874` and `frontend/src/pages/AIAssistantPage.tsx:52-104` use conditional mounts and bare `animate-in` keyframes or no motion. Desktop History lacks a matching exit; mobile History/backdrop teleport; rapid reversal restarts or removes the surface.

## Target

Keep lifecycle shells mounted through exit and use CSS transitions on opacity and transform. Enter with `--motion-ease-enter`; on-screen movement uses `--motion-ease-move` or `--motion-ease-drawer`. Drawer duration is `--motion-duration-panel`; smaller fades use `--motion-duration-standard`. Mobile History translates from the right edge; backdrop opacity is coordinated. Reduced motion removes translation and keeps short visibility/opacity feedback.

## Repo conventions to follow

- Preserve current ownership, localStorage preference, Escape/backdrop/close behavior, responsive breakpoint, and focus restoration.
- Use no new dependency.

## Steps

1. Replace bare Assistant `animate-in` keyframes with transitionable state classes.
2. Add a reusable presence/lifecycle hook if needed to retain content through exit.
3. Implement desktop History, mobile History, and backdrop open/close/reversal.
4. Add route-change, focus-restoration, scroll-lock, and rapid-reversal tests.

## Boundaries

- Do not animate command-palette keyboard toggles.
- Do not add bounce, scale-from-zero, blur, or large choreography.

## Verification

- Desktop and 390×844 Playwright open/close/reverse sequences.
- Escape, backdrop, close button, route change, focus restoration, and body cleanup must pass.
- Reduced motion: no panel translation.
