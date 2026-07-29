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
| Botanical surface / active selection | `#0D1B0C` |
| Botanical surface subtle | `#091108` |
| Border | `#1B2419` |
| Strong border | `#293827` |
| Botanical border | `#355E2C` |
| Primary text | `#F5F7F3` |
| Heading text | `#FFFFFF` |
| Secondary text | `#A8B0A5` |
| Muted text | `#788075` (non-essential content only) |
| Botanical primary / marker | `#68A94F` |
| Botanical active / focus | `#77AD66` |
| Botanical muted | `#5F8D51` |
| Botanical soft text | `#A5C99A` |
| Utility label | `#E4E9E1` |
| Utility icon | `#6FA95C` |
| User message | `#3E6734` to `#47763A` |
| Citation fill / text | `#11200F` / `#82B96F` |
| Grounded-response identity | `#5D9C49` |

Use these values through semantic variables only. The page canvas must not
become navy, generic charcoal, or a large grey block. Cards use small surface
steps and soft black shadows instead of bright outlines. The sidebar is only
slightly separated from the canvas; the selected destination uses a quiet
green-black fill and a slim botanical marker.

Dark green intensity follows surface area and semantic importance:

- large message and selection surfaces use the darkest, most desaturated
  botanical values;
- medium selected states use soft green text and restrained active icons;
- the brightest botanical green is reserved for small markers, enabled primary
  actions, and compact identity accents;
- utility labels remain near-neutral while utility icons carry the green cue;
- citation badges use a dark fill and border so repeated references remain
  discoverable without competing with the answer.

Brand green remains distinct from semantic success. Information stays blue,
warnings stay amber, destructive states stay red, and success uses its
dedicated status token.

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

The lower utility area of the global sidebar contains one shared, directly
interactive Appearance segmented control above the profile and logout actions:

- expanded desktop uses an equal-width horizontal Light/System/Dark control
  with visible labels and Sun, Monitor, and Moon icons;
- collapsed desktop uses the same component as a centered vertical,
  icons-only three-position control with a tooltip and accessible name for each
  mode;
- mobile uses the horizontal control at full available width and hides only the
  visible option labels when its own container is 270px or narrower;
- a single selection thumb moves behind the options. Its selected position
  represents the stored preference, so System remains selected when its
  resolved palette changes;
- the component is a labelled radio group with roving tab focus. Left/Right
  navigate the horizontal form, Up/Down navigate the vertical form, Home
  selects Light, End selects Dark, and native Enter/Space button activation is
  preserved;
- choosing a mode in the mobile drawer does not close the drawer, and changing
  sidebar orientation does not replace the focused option.

This replaces the former inert `Theme & Settings` row. No second competing
appearance control is introduced.

The control uses dedicated semantic variables in `src/index.css`. Light mode
uses track `#EEF2EC`, thumb `#FFFFFF`, border `#D8E0D4`, selected text
`#182116`, inactive text `#687064`, and selected icon `#4F843D`. Dark mode uses
track `#060906`, thumb `#121812`, border `#263124`, selected text `#F4F7F2`,
inactive text `#7D877A`, and selected icon `#82B36F`.

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
- expanded, collapsed, keyboard, and mobile drawer segmented controls;
- dashboard, assistant, Knowledge Center, real document viewer, workspace,
  saved knowledge, summaries, admin, system monitor (when authorized), and auth;
- tooltip, dialog, command palette, toast/portal inheritance;
- absolute-black canvas, foreground contrast, white-surface exceptions, console
  errors, failed requests, and startup flash sampling.

The default artifact path is `outputs/playwright/dark-mode/`. The validated
botanical refinement evidence is in
`outputs/playwright/dark-green-refinement/`, including matched-viewport
before/after captures, computed-style evidence, interaction states, and a
machine-readable verifier result.

## Verification status

Last verified on 2026-07-29:

- `pnpm.cmd run typecheck`: passed;
- `pnpm.cmd test`: 76 passed, 0 failed;
- production Vite build: passed using an isolated validation output directory
  because the normal Windows `dist` asset was held open by another process;
- `node scripts/verify_appearance_toggle.mjs`: 20 passed, 0 failed, including
  expanded/collapsed/mobile geometry, persistence, keyboard behavior, focus
  restoration, System live updates, reduced motion, console, and network
  checks;
- `node scripts/verify_dark_mode.mjs`: passed, including botanical-token
  hierarchy, startup flash, route, mobile, keyboard, portal, and native-document
  checks in the most recent retained dark-mode audit. The standalone script is
  not present in this repository snapshot; its retained machine-readable
  evidence remains under `outputs/playwright/dark-mode/`.

Admin and System Monitor were covered through their role-gated Access Denied
state because the verification account is intentionally non-admin. The
verifier's short live assistant answer did not include a citation; a separate
long-answer Playwright audit produced six live citations and exercised headings,
lists, a table, inline code, a code block, blockquote, related questions,
history, and the floating composer.
