# 003 — Keep Assistant resizing attached to the pointer

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: HIGH
- **Category**: Performance, interruptibility
- **Estimated scope**: 3–4 files

## Problem

`frontend/src/components/assistant/ChatPanel.tsx:845-861` transitions panel geometry for 200ms while `onResize` changes size continuously. `frontend/src/components/assistant/ChatMessage.tsx:353-369` applies `transition-all` to width and margins, so answer geometry chases the pointer.

## Target

During active pointer resize, panel flex/width and answer width/margins update with no transition. Preserve only property-scoped transitions for discrete non-drag state changes. Maintain limits, saved panel size, breakpoints, pointer cleanup, and cancellation.

## Repo conventions to follow

- Continue using `react-resizable-panels` and existing IDs/storage.
- Use shared tokens only for discrete state changes.

## Steps

1. Track active resizing using the panel group/handle callbacks or pointer lifecycle.
2. Remove `transition-[flex-grow]` from continuous geometry and `transition-all` from answer cards.
3. Add a scoped class/data attribute that guarantees transitions are off while dragging.
4. Add pointer-drag regression coverage.

## Boundaries

- Do not replace the panel library or change sizing limits/persistence.
- Do not change answer typography or responsive width rules.

## Verification

- Playwright pointer drag: panel and answer geometry must match each sampled pointer position without a 200ms tail.
- Rapid drag cancellation and breakpoint changes must clean up resizing state.
