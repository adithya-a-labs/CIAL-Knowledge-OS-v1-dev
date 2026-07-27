# Appearance and Theme System

This document is the canonical appearance contract for the CIAL Knowledge OS
frontend. It extends the [Design Language](DESIGN_LANGUAGE.md) without changing
the product's calm, enterprise visual direction.

## Supported appearance modes

CIAL Knowledge OS supports three explicit preferences:

- **Light** uses the light token set regardless of the operating-system setting.
- **System** follows `prefers-color-scheme` and updates while the application is
  open when the operating-system setting changes.
- **Dark** uses the dark token set regardless of the operating-system setting.

`System` is the default when no preference has been stored. Resolving the system
setting does not replace it with an explicit Light or Dark preference.

## Persistence and startup

- `next-themes` owns runtime theme state with `attribute="class"`,
  `defaultTheme="system"`, `enableSystem`, and `storageKey="cial-theme"`.
- The preference is browser/device-scoped. It is not currently synchronized to
  the authenticated user-preference API.
- The selected preference survives routes, direct URLs, reloads, authentication
  transitions, logout/login, and expanded/collapsed navigation.
- A small document-head bootstrap applies the resolved root class and
  `color-scheme` before the Vite entry module executes. It reads but never
  invents or overwrites `cial-theme`.
- The root document receives `.dark` only when the resolved appearance is dark.

## Semantic token strategy

`src/index.css` is the frontend token source of truth. Application components
must prefer semantic utilities such as `bg-background`, `bg-card`,
`bg-popover`, `text-foreground`, `text-muted-foreground`, `border-border`,
`bg-muted`, `bg-accent`, and the status tokens over literal neutral colors.

The token families cover:

- application, card, popover, input, border, and sidebar surfaces;
- primary, secondary, muted, accent, destructive, and focus states;
- chart series and chart chrome;
- success, warning, information, and citation states;
- code blocks, selections/highlights, overlays, scrollbars, and elevation.

Literal colors remain acceptable only for intentional source content, file-type
identity, illustrations, and native document-paper surfaces. PDF pages and
images are never filtered or inverted.

## Dark palette and expression

Dark mode is a nighttime botanical expression of the light interface, not a
literal color inversion. Absolute black remains the canvas while green-black
surfaces, restrained botanical borders, soft typography, and low-opacity forest
radials restore the hierarchy and atmosphere present in light mode.

| Role | Dark value |
| --- | --- |
| Canvas | `#000000` |
| Sidebar | `#020402` |
| Surface 1 / card | `#050705` |
| Surface 2 / raised popover | `#090D08` |
| Hover | `#0D140C` |
| Active selection | `#122010` |
| Border | `#1B2419` |
| Strong border | `#293827` |
| Primary text | `#F5F7F3` |
| Heading text | `#FFFFFF` |
| Secondary text | `#A8B0A5` |
| Muted text | `#788075` (non-essential content only) |
| Brand | `#78C45A` |
| Brand strong | `#8AD167` |

Use these values through semantic variables only. The page canvas must not
become navy, generic charcoal, or a large grey block. Cards use small surface
steps and soft black shadows instead of bright outlines. The sidebar is only
slightly separated from the canvas; the selected destination uses a quiet
green-black fill and a slim botanical marker.

The application shell may use extremely subtle forest-green ambient radials to
keep large black areas from feeling empty. They must never read as a gradient
hero or compete with content.

### Typography and content surfaces

- Headings use the near-white heading token; body copy uses the softer primary
  text token; metadata uses secondary or muted tokens according to importance.
- Assistant markdown, notes, and document analysis share the same semantic
  blockquote rule, code surfaces, table borders, row hover, and citation chips.
- Native PDF pages, images, presentation slides, and source-authored paper
  remain faithful and may stay light. Only the surrounding application chrome
  adopts dark mode; source content is never inverted.

### Elevation and the composer exception

Dialogs, dropdowns, command surfaces, and tooltips use Surface 2, a botanical
border, a subtle inner highlight, and a soft black shadow. The AI composer is
the one intentional, restrained liquid-glass exception to the general rule
against glassmorphism: it floats over a transparent-to-black dock with a
near-black translucent surface and modest blur. It must never sit inside a
large opaque footer slab.

## Appearance control

The lower utility area of the global sidebar contains one shared Appearance
control above the profile and logout actions:

- expanded desktop and mobile show the `Appearance` label, selected mode, and
  matching Sun, Monitor, or Moon icon;
- collapsed desktop preserves rail geometry with an icon-only trigger and an
  `Appearance` tooltip;
- the dropdown contains Light, System, and Dark radio items with a visible
  selected indicator;
- the collapsed menu opens to the right;
- accessible trigger names include the selected preference, for example
  `Appearance: System`;
- keyboard support follows the Radix menu contract: Tab reaches the trigger,
  Enter/Space opens it, arrows move, Enter selects, and Escape closes and
  restores focus;
- choosing a mode in the mobile drawer does not close the drawer.

This replaces the former inert `Theme & Settings` row. No second competing
appearance control is introduced.

## Accessibility and motion

- Text, focus, status, selection, disabled, hover, and active states target
  WCAG 2.2 AA contrast.
- Status is communicated with text/iconography as well as color.
- Theme controls expose their current preference through their accessible name
  and checked menu item.
- Theme changes do not use a long whole-page fade. Startup resolution suppresses
  transition artifacts, and existing `prefers-reduced-motion` behavior remains
  authoritative.
- Dark interactions use `140–180ms` transitions. Pressed movement is limited to
  one pixel, and reduced-motion removes non-essential transitions and movement.

## Playwright coverage

The repository dark-mode verifier covers:

- System/light and System/dark resolution;
- explicit Light, Dark, and System selection and persistence;
- route, reload, direct-URL, and logout/login continuity;
- expanded, collapsed, keyboard, and mobile drawer controls;
- dashboard, assistant, Knowledge Center, real document viewer, workspace,
  saved knowledge, summaries, admin, system monitor (when authorized), and auth;
- dropdown, tooltip, dialog, command palette, toast/portal inheritance;
- absolute-black canvas, foreground contrast, white-surface exceptions, console
  errors, failed requests, and startup flash sampling.

The default artifact path is `outputs/playwright/dark-mode/`. The validated
botanical refinement evidence is in
`outputs/playwright/dark-mode-refinement/`, including matched light/dark
screenshots, before/after captures, and a machine-readable verifier result.

## Verification status

Last verified on 2026-07-28:

- `pnpm.cmd run typecheck`: passed;
- `pnpm.cmd test`: 74 passed, 0 failed;
- production Vite build: passed using an isolated validation output directory
  because the normal Windows `dist` asset was held open by another process;
- `node scripts/verify_dark_mode.mjs`: passed, including botanical-token
  hierarchy, startup flash, route, mobile, keyboard, portal, and native-document
  checks, with no required failures, unexpected console errors, or unexpected
  failed requests.

Admin and System Monitor were covered through their role-gated Access Denied
state because the verification account is intentionally non-admin. The
verifier's short live assistant answer did not include a citation; a separate
long-answer Playwright audit produced six live citations and exercised headings,
lists, a table, inline code, a code block, blockquote, related questions,
history, and the floating composer.
