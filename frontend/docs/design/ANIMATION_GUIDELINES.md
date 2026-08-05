# Animation Guidelines

Motion in CIAL Knowledge OS is quiet, useful, and deliberate. It provides feedback, preserves spatial continuity, or explains a state change; it does not decorate routine work.

## Source-of-truth tokens

`src/index.css` owns the shared motion vocabulary:

| Token | Value | Use |
| --- | --- | --- |
| `--motion-duration-press` | `140ms` | Direct press and lightweight hover feedback |
| `--motion-duration-short` | `160ms` | Small control and disclosure state changes |
| `--motion-duration-standard` | `180ms` | Synchronized component state changes |
| `--motion-duration-panel` | `220ms` | Reversible panel, drawer, and backdrop lifecycles |
| `--motion-ease-enter` | `cubic-bezier(0.23, 1, 0.32, 1)` | Content entering from rest |
| `--motion-ease-move` | `cubic-bezier(0.77, 0, 0.175, 1)` | Symmetric movement between known states |
| `--motion-ease-drawer` | `cubic-bezier(0.32, 0.72, 0, 1)` | Reversible spatial panels and drawers |

Use the shared custom properties directly for custom CSS. Tailwind utilities remain acceptable when they resolve to the same duration and property-specific behavior. Do not introduce one-off timing curves for ordinary application motion.

## Motion decision test

Use motion only when it improves at least one of these outcomes:

- immediate interaction feedback;
- spatial continuity between open and closed states;
- comprehension of a meaningful state change;
- progress or loading communication.

Static state changes are preferable when motion would be decorative, repeat on a high-frequency keyboard action, or delay access to content.

## Property and lifecycle rules

- Transition only the properties that actually change. `transition: all` and `transition-all` are prohibited in application code.
- Prefer compositor-friendly `transform` and `opacity`. Animate color, border color, and shadow only for lightweight state feedback.
- Do not animate layout during direct manipulation. Resize handles and pointer drags track the pointer without easing or lag.
- Panels, drawers, backdrops, and variable-height disclosures must support both entry and exit. A closing surface may stay mounted only for its exit duration, must be non-interactive and hidden from assistive technology while closing, and must unmount afterward.
- Reopening during an exit retargets the transition from the current visual state; it must not restart from a hard-coded origin.
- Transform origins must match the surface's physical attachment edge.
- Avoid `scale(0)`, bounce, exaggerated springs, decorative lift, and long or delayed motion.
- Keyboard navigation and high-frequency repeated actions must remain immediate.

## Assistant behavior

The conversation viewport auto-follows only while the reader is already near the bottom. New messages, streaming deltas, and loading-state changes must not pull a reader away from earlier content. Sending a new prompt re-enables follow intentionally. Programmatic scrolling uses instant behavior when `prefers-reduced-motion: reduce` is active.

Assistant history, source/document panes, and mobile drawers use reversible lifecycles. Desktop panel resizing is direct manipulation and therefore carries no width, margin, or flex transition during drag.

## Component conventions

- Variable-height accordions use a content-sized grid-row transition rather than a fixed `max-height`. The disclosure remains mounted for rapid reversal, exposes `aria-expanded` and `aria-controls`, and makes collapsed descendants inert.
- Knowledge Graph node hover changes only a compositor-friendly, fill-box-centered transform. SVG radius, stroke paint, and filter effects do not transition during repeated pointer movement; selected-state paint remains discrete and legible.
- Non-interactive FAQ cards remain spatially static. Hover and focus feedback belongs to the actual button or link.
- Appearance-control geometry, thumb travel, icon color, and label color share the standard `180ms` movement timing. Reduced motion removes thumb travel.

## Reduced motion

Reduced motion is a targeted policy, not a universal near-zero duration clamp.

- Remove spatial translation, transform-driven travel, smooth scrolling, decorative motion, and non-essential keyframes.
- Preserve immediate state visibility and useful non-spatial feedback such as color, border, focus, selection, and opacity where it does not imply travel.
- JavaScript-initiated scrolling and lifecycle code must query the same media preference instead of relying only on CSS.
- Components must remain fully operable and must not depend on `transitionend` firing to expose content or restore focus.

## Review checklist

Before shipping motion, verify normal and reduced-motion modes, opening and closing, rapid reversal, route changes, breakpoint changes, keyboard and touch input, focus restoration, and cleanup after unmount. Motion must preserve the calm, premium enterprise design language and make the interface easier to understand.

The motion regression covers desktop assistant history and resizing, streaming auto-follow, appearance synchronization, source accordion disclosure, repeated graph hover, the mobile History drawer, touch document overlays and rotation, reduced-motion behavior, console/network failures, focus restoration, overflow, and stale overlay cleanup.

Run the deterministic contracts and browser regressions from `frontend/`:

```powershell
pnpm.cmd test
pnpm.cmd run verify:motion
pnpm.cmd run verify:appearance
pnpm.cmd run verify:mobile-lifecycle
```

The motion verifier writes its machine-readable result to `outputs/playwright/motion-system/`. Browser fixtures use authenticated same-origin API interception and a paced NDJSON stream so scroll-follow behavior is measured during real incremental rendering rather than inferred from static source.
