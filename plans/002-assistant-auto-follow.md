# 002 — Make Assistant auto-follow user-controlled

- **Status**: DONE
- **Commit**: 51edafa
- **Severity**: HIGH
- **Category**: Purpose, frequency, accessibility
- **Estimated scope**: 2–3 files

## Problem

`frontend/src/components/assistant/ChatPanel.tsx:181-189` calls `scrollIntoView({ behavior: 'smooth' })` whenever messages, loading state, or the one-second request clock changes. Token updates at `ChatPanel.tsx:412-424` also mutate messages, repeatedly restarting smooth scrolling and pulling users back after intentional upward scrolling.

## Target

Track whether the scroll viewport is near its bottom. Follow incremental streaming only while near the bottom; never force follow after the user scrolls upward. A newly submitted user message may explicitly re-enable follow. Use instant scrolling for incremental updates and for all reduced-motion users; at most one restrained smooth scroll may occur for a discrete new-user-message action when motion is allowed.

## Repo conventions to follow

- Preserve `chatMessagesRef`, request runtime ownership, streaming batching, cancellation, retry, and timing.
- Reuse the shared reduced-motion hook/token vocabulary from plan 001.

## Steps

1. Track near-bottom state from the actual chat scroll container.
2. Remove `requestClock` and broad message-object changes as scroll triggers.
3. Separate discrete new-user-message follow from incremental stream follow.
4. Add tests for manual upward scrolling, resuming at bottom, streamed updates, and reduced motion.

## Boundaries

- Do not alter chat API calls, payloads, streaming, cancellation, retries, or message persistence.
- Do not animate keyboard-triggered high-frequency updates.

## Verification

- Playwright: stream a multi-token response and count scroll calls; manually scroll upward and verify scrollTop remains stable; return near bottom and verify following resumes.
- Reduced motion must produce no smooth scroll calls.
- Done when request-clock and token updates cannot repeatedly restart smooth scrolling.
