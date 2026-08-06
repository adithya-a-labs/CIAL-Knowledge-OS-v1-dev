# Responsive Navigation and Modal Lifecycle

## Source of truth

`frontend/src/components/layout/AppShell.tsx` owns the global navigation mode
and the single controlled `mobileOpen` state. The desktop rail begins at
`1024px`; the mobile navigation is valid only while
`(max-width: 1023px)` matches. A route change or transition into the desktop
breakpoint closes that state. Returning to a compact viewport never reopens a
drawer from stale orientation state.

`frontend/src/components/layout/MobileSidebarDrawer.tsx` renders that state
through the shared Radix `Sheet`. It must not write `document.body` or
`document.documentElement`, add a second focus trap, or hide an open modal with
responsive CSS. Radix owns overflow, pointer-event, aria-hidden, focus guard,
Escape, outside-click, and focus-restoration cleanup while the controlled sheet
is open.

The shared Sheet uses the existing motion tokens: panel entry/exit is `220ms`
with `cubic-bezier(0.32, 0.72, 0, 1)`, and the backdrop uses the shorter
`180ms` entrance curve. It enters and exits through its attachment edge.
Reduced motion removes the spatial keyframes without changing Radix ownership,
focus restoration, scroll-lock cleanup, or final unmount behavior.

Every global navigation item closes the sheet before navigation. Logout closes
it before invalidating authentication. The Search action closes the sheet and
opens the command dialog from Radix's `onCloseAutoFocus` cleanup boundary;
Ctrl/Cmd+K does not open
the command dialog while another dialog or `aria-modal` surface is active. This keeps one
scroll-lock owner at a time.

## Document workspace panels

`frontend/src/pages/DocumentWorkspacePage.tsx` separately owns Corpus Tree and
Document Assistant state. Corpus Tree becomes persistent at `1280px` and the
Document Assistant at `1024px`. Media-query change handlers reset incompatible
overlay state, only one compact overlay can be opened at once, and route
unmount removes its overlay and focus listener. Below `1024px`, the document
toolbar retains a leading inset for the fixed global-navigation trigger so the
Corpus Tree control remains a separate touch target.

Compact workspace overlays use a reversible `220ms` lifecycle. Closing first
makes the backdrop and panel non-interactive and hidden from assistive
technology, then unmounts them after the exit transition. Reopening during that
window cancels unmount and retargets from the current visual state. Escape,
outside-click, close-button, breakpoint, route, refresh, and unmount paths all
use the same cleanup boundary. Reduced motion removes spatial travel without
changing focus restoration, modal ownership, or final unmount behavior.

## Required lifecycle checks

The settled closed state, after the bounded exit lifecycle, has no inline
body/html overflow or pointer-events, no
`data-scroll-locked`, no unexpected inert nodes, no hidden dialog, and no
invisible full-screen overlay. An open Radix sheet may temporarily own those
library-managed protections, but all must be restored after close, navigation,
rotation, refresh, logout, error, or unmount.

Run the deterministic source contracts and touch-emulated browser regression:

```powershell
pnpm.cmd test -- tests/mobile-modal-lifecycle.test.mjs
$env:CIAL_MOBILE_TEST_URL='http://127.0.0.1:4174'
pnpm.cmd run verify:mobile-lifecycle
```

The browser regression covers the shared Sheet's computed duration/easing,
iPad portrait and landscape initial loads, both
orientation transitions, login, refresh, global navigation, serialized search
handoff, route changes, Corpus Tree, Document Assistant, logout, restored
background scrolling, and body/modal cleanup.
