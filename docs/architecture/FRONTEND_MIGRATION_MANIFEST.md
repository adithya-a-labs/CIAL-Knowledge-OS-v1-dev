# Frontend Migration Manifest

## Current integrated frontend appearance state

Verified on 2026-07-28 against the integrated application in `frontend/`:

- Light, System, and Dark are implemented with `next-themes`; System is the
  default and follows live operating-system color-scheme changes.
- The browser-scoped preference is stored as `cial-theme`, is applied before
  application startup, and persists through routes, reloads, direct URLs, and
  authentication transitions.
- `frontend/src/index.css` is the semantic token source of truth. Dark mode is a
  validated nighttime botanical expression: the application canvas remains
  absolute black while sidebar, card, raised, hover, active, and border roles
  use progressively lighter green-black tokens.
- One shared, keyboard-accessible Appearance control is present in expanded,
  collapsed, and mobile navigation.
- Native source documents remain visually faithful: PDF/image content is not
  inverted, and intentional document-paper surfaces are explicitly marked.
- Assistant markdown, notes, portals, Knowledge Center, native document chrome,
  mobile navigation, auth, and role-gated admin screens were included in the
  refinement audit. Native source pages remain unfiltered.
- The detailed implementation contract is
  [`frontend/docs/design/THEMING.md`](../../frontend/docs/design/THEMING.md).
  Automated coverage lives in `scripts/verify_dark_mode.mjs` and writes its
  default report/screenshots to `outputs/playwright/dark-mode/`; the validated
  refinement evidence is under `outputs/playwright/dark-mode-refinement/`.

The remaining sections preserve the original source-repository migration
inventory; this verified integrated state supersedes historical light-only
statements in that inventory.

## 1. Executive Summary

This repository is a Replit/pnpm workspace containing a frontend artifact, mockup sandbox, backend/API scaffolding, generated build output, local Replit state, and design documentation.

The production frontend migration source of truth is:

- `artifacts/cial-dashboard`
- `artifacts/cial-dashboard/src`
- `artifacts/cial-dashboard/public`
- `artifacts/cial-dashboard/index.html`
- `artifacts/cial-dashboard/package.json`
- `artifacts/cial-dashboard/vite.config.ts`
- `artifacts/cial-dashboard/tsconfig.json`
- `artifacts/cial-dashboard/components.json`
- `artifacts/cial-dashboard/.env.example`
- `docs/design`

The frontend is currently a mostly mocked/static React dashboard. It has a React Query provider and a generated API client package exists in `lib/api-client-react`, but dashboard pages currently consume local `src/data/*` mock/static data rather than backend REST endpoints.

Do not migrate Replit local state, generated build output, `node_modules`, `.tsbuildinfo`, or the mockup sandbox unless intentionally preserving historical prototype references.

## 2. Repository Overview

| Path | Classification | Notes |
|---|---:|---|
| `artifacts/cial-dashboard` | Required | Main frontend application. |
| `artifacts/cial-dashboard/src` | Required | React source: routes, pages, layouts, components, data, config, hooks, utilities, types, styling entry. |
| `artifacts/cial-dashboard/public` | Required | Runtime public assets: CIAL logo, favicon, Open Graph image, robots file. |
| `artifacts/cial-dashboard/dist` | Generated | Vite build output. Exclude. |
| `artifacts/cial-dashboard/.replit-artifact` | Ignore | Replit artifact metadata. |
| `artifacts/mockup-sandbox` | Optional / Development Only | Prototype/mockup sandbox. Not required for production migration. |
| `artifacts/mockup-sandbox/dist` | Generated | Exclude. |
| `artifacts/api-server` | Ignore for frontend migration | Backend scaffold, not frontend source. |
| `artifacts/api-server/dist` | Generated | Exclude. |
| `lib/api-client-react` | Optional / API reference | Generated React Query API client package. Currently not used by dashboard pages, but useful migration pattern. |
| `lib/api-spec` | Optional / API reference | OpenAPI spec and Orval config. Current spec only exposes `/api/healthz`. |
| `lib/api-zod` | Optional / Backend/API reference | Generated Zod API schemas. |
| `lib/db` | Ignore for frontend migration | Database package for backend. |
| `docs/design` | Required / Optional design source | Strongly recommended to migrate as design documentation. |
| `attached_assets` | Optional / Reference Only | Replit prompt/reference screenshots and pasted task files. Not imported by dashboard source. |
| `.agents` | Ignore | Agent memory/state. |
| `.local` | Ignore | Replit/local workflow state and pnpm store cache. |
| `node_modules` | Generated | Exclude. |
| `scripts` | Development Only | Workspace helper scripts; not required for migrated frontend runtime. |

## 3. Required Folders

### `artifacts/cial-dashboard/src`

Required. This is the main frontend source.

| Folder | Classification | Purpose |
|---|---:|---|
| `src/pages` | Required | Route-level pages. |
| `src/components/layout` | Required | App shell, sidebar, top bar, mobile drawer. |
| `src/components/common` | Required | Shared dashboard UI primitives such as cards, search, filters, empty states, tables. |
| `src/components/ui` | Required | shadcn/Radix-style local component library. |
| `src/components/dashboard` | Required | Dashboard hero, KPI row, dashboard blocks. |
| `src/components/dashboard/blocks` | Required | Dashboard content block components. |
| `src/components/assistant` | Required | AI Assistant UI with PostgreSQL-backed authenticated history, live chat, citations, context manager, and retrieval timeline. |
| `src/components/documents` | Required | Document card/row/upload modal UI. |
| `src/components/knowledge-center` | Required | Main Knowledge Center implementation. |
| `src/components/workspace` | Required | My Workspace feature components. |
| `src/config` | Required | App, theme, navigation, dashboard, security, user config. Mostly static/mock. |
| `src/data` | Required for current UI | Static/mock data backing the frontend. Replace with API calls during integration. |
| `src/data/workspace` | Required for current UI | Workspace mock data, permissions, storage utilities, types. |
| `src/hooks` | Required | `use-mobile`, `use-toast`. |
| `src/lib` | Required | `utils.ts`, including class name utility. |
| `src/types` | Required | Shared TypeScript types. |
| `src/components/assets` | Ignore / Empty | Folder exists but contains no files. |

### Required source files

| File | Classification | Notes |
|---|---:|---|
| `src/main.tsx` | Required | React entrypoint. |
| `src/App.tsx` | Required | Router, React Query provider, tooltip/toast providers, route map. |
| `src/index.css` | Required | Tailwind v4 entry, design tokens, CIAL theme, utility classes. |
| `src/types.ts` | Required | Shared application types. |
| `src/types/index.ts` | Required | Shared exported types. |
| `src/types/assistant.ts` | Required | Assistant-specific types. |

## 4. Required Files

| File | Classification | Notes |
|---|---:|---|
| `artifacts/cial-dashboard/index.html` | Required | Vite HTML entrypoint, metadata, Inter Google Font, favicon. |
| `artifacts/cial-dashboard/package.json` | Required | Frontend dependency and script source of truth. |
| `artifacts/cial-dashboard/vite.config.ts` | Required with edits | Vite, React, Tailwind, aliases, output path. Remove Replit plugins for production migration. |
| `artifacts/cial-dashboard/tsconfig.json` | Required with edits | TypeScript config. References `../../lib/api-client-react`. Adjust if new repo does not use this workspace package. |
| `artifacts/cial-dashboard/components.json` | Required | shadcn-style component aliases and Tailwind CSS entry config. |
| `artifacts/cial-dashboard/.env.example` | Required | Captures intended API/auth/AI feature flags. |
| `artifacts/cial-dashboard/public/*` | Required | Logo, favicon, Open Graph image, robots. |

## 5. Optional Files

| File/Folder | Classification | Notes |
|---|---:|---|
| `docs/README.md` | Optional | Index for design docs. |
| `docs/design/ANIMATION_GUIDELINES.md` | Optional but recommended | Motion rules. |
| `docs/design/COMPONENT_LIBRARY.md` | Optional but recommended | Component conventions. |
| `docs/design/DESIGN_LANGUAGE.md` | Optional but recommended | Primary UI design source of truth. |
| `docs/design/ICONOGRAPHY.md` | Optional but recommended | Icon usage guidance. |
| `docs/design/PAGE_PATTERNS.md` | Optional but recommended | Page layout conventions. |
| `docs/design/UX_PRINCIPLES.md` | Optional but recommended | UX principles. |
| `lib/api-client-react/src/custom-fetch.ts` | Optional / API reference | Robust fetch wrapper with base URL and auth token hooks. |
| `lib/api-client-react/src/generated/*` | Generated / Optional reference | Orval-generated React Query hooks. Current spec only has health check. |
| `lib/api-spec/openapi.yaml` | Optional / API reference | Current API contract stub. Replace with backend Phase 4.5 OpenAPI. |
| `lib/api-spec/orval.config.ts` | Optional / API reference | Codegen setup for React Query and Zod clients. |
| `attached_assets/*` | Optional / Reference Only | Screenshots and pasted prompt/task files from Replit. Not runtime assets. |
| `artifacts/mockup-sandbox` | Optional / Development Only | Prototype sandbox, not production migration source. |

## 6. Assets to Migrate

Required runtime assets:

| Asset | Classification | Notes |
|---|---:|---|
| `artifacts/cial-dashboard/public/cial-logo.png` | Required | Used by `src/config/appConfig.ts`, `src/config/themeConfig.ts`, and `src/data/adminData.ts`. |
| `artifacts/cial-dashboard/public/favicon.svg` | Required | Referenced by `index.html`. |
| `artifacts/cial-dashboard/public/opengraph.jpg` | Optional / Recommended | Social preview asset. |
| `artifacts/cial-dashboard/public/robots.txt` | Optional | Public robots file. |

Reference-only assets:

| Asset | Classification | Notes |
|---|---:|---|
| `attached_assets/image_*.png` | Optional / Reference Only | Replit development screenshots/reference images. No source imports found. |
| `attached_assets/Pasted-*.txt` | Optional / Reference Only | Original Replit prompts/tasks. Do not treat as app source. |

Fonts:

| Font | Classification | Notes |
|---|---:|---|
| Google Font `Inter` | Required | Loaded in `index.html`. For production, consider self-hosting or approved CDN policy. |
| CSS fallback stack | Required | Defined in `src/index.css` as `Inter`, `Segoe UI`, `system-ui`, `sans-serif`. |

Icons:

| Library | Classification | Notes |
|---|---:|---|
| `lucide-react` | Required | Primary icon library throughout pages/components/data. |
| `react-icons` | Optional / Review | Declared dependency, but no usage found in `artifacts/cial-dashboard/src`. Can likely omit if unused after migration. |

## 7. Configuration Files

| File | Classification | Notes |
|---|---:|---|
| `package.json` | Development Only / Workspace | Root pnpm workspace scripts and TypeScript/Prettier dev deps. Required only if preserving monorepo layout. |
| `pnpm-workspace.yaml` | Development Only / Workspace | Workspace packages, dependency catalog, Replit/Linux-specific overrides. Migrate selectively. |
| `pnpm-lock.yaml` | Required if preserving pnpm versions | Lockfile for reproducible install. Regenerate in integrated repo if dependency graph changes. |
| `tsconfig.base.json` | Required if preserving workspace TS setup | Shared strict TS settings. |
| `tsconfig.json` | Development Only / Workspace | Root project references for libs. |
| `.npmrc` | Optional | `auto-install-peers=false`, `strict-peer-dependencies=false`. |
| `.gitignore` | Required as reference | Contains appropriate generated exclusions and Replit local exclusions. |
| `artifacts/cial-dashboard/vite.config.ts` | Required with edits | Remove Replit plugin imports and conditional Replit plugin block for production. |
| `artifacts/cial-dashboard/tsconfig.json` | Required with edits | Adjust paths/references for integrated repo. |
| `artifacts/cial-dashboard/components.json` | Required | shadcn aliases and CSS path. |
| `artifacts/cial-dashboard/.env.example` | Required | Environment contract. |

Not found:

- No ESLint config found.
- No Prettier config found.
- No PostCSS config found.
- No `tailwind.config.*` found. This project uses Tailwind v4 via CSS and `@tailwindcss/vite`.

## 8. Package/Dependency Files

Frontend package:

- `artifacts/cial-dashboard/package.json` is the main dependency source.
- Root `pnpm-lock.yaml` pins the resolved workspace dependency graph.
- Root `pnpm-workspace.yaml` defines catalog versions used by `catalog:` dependency entries.

Dependency summary:

| Category | Dependencies |
|---|---|
| React | `react`, `react-dom`, `@vitejs/plugin-react` |
| Build | `vite`, `typescript`, `@types/react`, `@types/react-dom`, `@types/node` |
| Routing | `wouter` |
| Data/networking | `@tanstack/react-query`, `@workspace/api-client-react` |
| UI primitives | `@radix-ui/react-*`, `cmdk`, `vaul`, `react-resizable-panels`, `input-otp`, `react-day-picker`, `embla-carousel-react` |
| Styling | `tailwindcss`, `@tailwindcss/vite`, `@tailwindcss/typography`, `tw-animate-css`, `class-variance-authority`, `clsx`, `tailwind-merge` |
| Icons | `lucide-react`, declared `react-icons` |
| Charts | `recharts` |
| Forms/validation | `react-hook-form`, `@hookform/resolvers`, `zod` |
| Dates | `date-fns` |
| Notifications | local Radix toast components, `sonner` declared/available |
| Theme | Integrated Light/System/Dark system implemented with `next-themes`; see `frontend/docs/design/THEMING.md` |
| Animation | `framer-motion` declared, `tw-animate-css` imported |
| Replit development | `@replit/vite-plugin-cartographer`, `@replit/vite-plugin-dev-banner`, `@replit/vite-plugin-runtime-error-modal` |

Migration note: several dependencies are declared because the local shadcn-style UI library is broad. During production migration, re-check actual imports after route/page consolidation before carrying every dependency forward.

## 9. Replit-Specific Files

| File/Folder | Classification | Recommendation |
|---|---:|---|
| `.replit` | Development Only / Replit | Do not migrate to production integrated repo unless continuing on Replit. |
| `.replitignore` | Development Only / Replit | Do not migrate unless deploying with Replit. |
| `replit.md` | Development Only / Replit scaffold | Contains generic scaffold notes. Do not treat as product docs. |
| `.local` | Ignore | Local Replit state, workflow logs, pnpm store. Exclude. |
| `.agents` | Ignore | Agent memory files. Exclude. |
| `artifacts/*/.replit-artifact` | Ignore | Replit artifact metadata. Exclude. |
| Replit Vite plugins in `vite.config.ts` | Development Only | Remove from production config. |
| `attached_assets` | Optional / Reference Only | Replit prompt/screenshot artifacts. Not runtime source. |

## 10. Files to Explicitly Exclude

Exclude from frontend migration:

- `.git`
- `.local`
- `.agents`
- `node_modules`
- `scripts/node_modules`
- `lib/*/node_modules`
- `artifacts/*/node_modules`
- `dist`
- `artifacts/cial-dashboard/dist`
- `artifacts/mockup-sandbox/dist`
- `artifacts/api-server/dist`
- `*.tsbuildinfo`
- `.cache`
- `tmp`
- `out-tsc`
- `.expo`
- `.expo-shared`
- `coverage`
- `dev-server.err.log`
- `dev-server.out.log`
- `.replit-artifact`
- `artifacts/api-server` for frontend-only migration
- `lib/db` for frontend-only migration
- `lib/api-zod/dist`
- `lib/api-client-react/dist`
- `lib/db/dist`

## 11. Environment Variables

From `artifacts/cial-dashboard/.env.example`:

| Variable | Classification | Current status |
|---|---:|---|
| `VITE_API_BASE_URL` | Backend API base URL | Used by `frontend/src/api/client.ts`; loopback hosts are normalized to the current browser host for cookie-session reliability. |
| `VITE_AUTH_CLIENT_ID` | Future auth | Not currently wired. |
| `VITE_AUTH_TENANT_ID` | Future auth | Not currently wired. |
| `VITE_AUTH_REDIRECT_URI` | Future auth | Not currently wired. |
| `VITE_AI_API_ENDPOINT` | Future AI | Not currently wired. |
| `VITE_AI_MODEL_VERSION` | Future AI | Not currently wired. |
| `VITE_ENABLE_REAL_AI` | Feature flag | Defined, not currently wired. |
| `VITE_ENABLE_AUTH` | Feature flag | Defined for compatibility; auth is currently enforced through the backend HttpOnly cookie session. |

Other environment inputs used by config:

| Variable | Classification | Notes |
|---|---:|---|
| `PORT` | Development/deployment | Used by Vite config for dev/preview port. |
| `BASE_PATH` | Deployment | Used by Vite config as `base`. |
| `NODE_ENV` | Standard | Used to conditionally enable Replit plugins. |
| `REPL_ID` | Replit only | Used to conditionally enable Replit plugins. |

## 12. API Layer Status

Current status: the frontend remains mixed integration/static overall. Authentication, corpus, personal workspace, live chat, and conversation history are integrated APIs; other areas documented below still use static data.

Evidence:

- Dashboard pages/components import from `@/data/*`.
- `src/data/*` contains domain data for dashboard, documents, experts, FAQs, learning, analytics, admin, knowledge center, knowledge graph, knowledge gaps, assistant, SOPs, and workspace.
- `src/components/assistant/ChatPanel.tsx` calls the authenticated backend chat API. `AssistantSessionContext.tsx` hydrates only after authentication resolves and treats PostgreSQL history as authoritative; it has no seeded/default conversation fallback.
- `src/pages/DashboardPage.tsx` contains a TODO to replace mock homepage arrays with personalized API data.
- `src/config/securityConfig.ts` and `src/config/userConfig.ts` contain TODOs for Microsoft Entra ID / Keycloak integration.
- `@workspace/api-client-react` exists and exports React Query hooks generated from OpenAPI, but current dashboard source does not import it.
- The current OpenAPI spec only defines `GET /api/healthz`.

API migration recommendation:

- Keep the UI component/page structure.
- Replace `src/data/*` imports progressively with typed REST calls.
- Regenerate API hooks from the Phase 4.5 backend OpenAPI spec.
- Add one frontend API boundary, for example `src/api`, instead of scattering generated hook calls directly through all components.
- Keep `VITE_API_BASE_URL` wired through `frontend/src/api/client.ts`; local loopback hosts normalize to the current browser host to avoid `localhost`/`127.0.0.1` SameSite cookie loss.
- Keep `AuthProvider`, `frontend/src/api/client.ts`, and backend `/api/auth/*` aligned around the HttpOnly cookie session contract.

## 13. Risks During Migration

- The current UI depends heavily on static mock data shape. Backend DTOs may not match current frontend model names.
- `src/data/*` currently doubles as both mock content and frontend domain schema. Split real API types from view models during migration.
- Some page files are not currently routed directly: `DocumentsPage.tsx`, `PoliciesSOPsPage.tsx`, and `KnowledgeBasePage.tsx`. They may be legacy/alternate implementations and should be reviewed before carrying forward.
- `KnowledgeCenterPage.tsx` is a wrapper around `components/knowledge-center/KnowledgeCenter.tsx`, which contains a large implementation. Consider splitting only after migration parity is achieved.
- Replit plugins and metadata should not leak into production Vite config.
- `index.html`, `.env.example`, and some text content show encoding artifacts for punctuation/copyright symbols. Normalize encoding during migration.
- `VITE_*` variables are declared but not wired into the app yet.
- The root workspace contains backend/db/API scaffolding unrelated to the final frontend migration.
- Tailwind v4 is configured through CSS and `@tailwindcss/vite`, not a classic `tailwind.config.*`; migration tooling must support Tailwind v4.
- The project uses React 19.1.0 via pnpm catalog. Confirm target integrated repo React version before migration.

## 14. Recommended Integrated Frontend Structure

Recommended target structure:

```text
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  components.json
  .env.example
  public/
    cial-logo.png
    favicon.svg
    opengraph.jpg
    robots.txt
  src/
    main.tsx
    App.tsx
    index.css
    api/
      client.ts
      generated/
      adapters/
    components/
      assistant/
      common/
      dashboard/
      documents/
      knowledge-center/
      layout/
      ui/
      workspace/
    config/
    data/
      mock/
    hooks/
    lib/
    pages/
    types/
  docs/
    design/
```

Recommended treatment:

- Move current `src/data/*` under `src/data/mock` when real APIs are introduced.
- Add `src/api/client.ts` to configure base URL, auth, error handling, and generated API access.
- Keep `src/components/ui` local unless the integrated repo already has an equivalent design system.
- Keep `src/index.css` as the design token source until a formal theme package exists.
- Remove Replit plugins from Vite.
- Migrate design docs into integrated repo documentation.

## 15. Final Migration Checklist

- [ ] Migrate `artifacts/cial-dashboard/src`.
- [ ] Migrate `artifacts/cial-dashboard/public`.
- [ ] Migrate `artifacts/cial-dashboard/index.html`.
- [ ] Migrate and clean `artifacts/cial-dashboard/package.json`.
- [ ] Migrate and clean `artifacts/cial-dashboard/vite.config.ts`.
- [ ] Migrate and adapt `artifacts/cial-dashboard/tsconfig.json`.
- [ ] Migrate `artifacts/cial-dashboard/components.json`.
- [ ] Migrate `artifacts/cial-dashboard/.env.example`.
- [ ] Migrate `docs/design` as product/design reference docs.
- [ ] Decide whether to preserve pnpm workspace/catalog setup or flatten dependencies into the integrated repo.
- [ ] Remove Replit-specific Vite plugins and metadata.
- [ ] Exclude `node_modules`, `dist`, `.local`, `.agents`, `.replit-artifact`, and `*.tsbuildinfo`.
- [ ] Review unused/legacy pages: `DocumentsPage.tsx`, `PoliciesSOPsPage.tsx`, `KnowledgeBasePage.tsx`.
- [ ] Replace mock `src/data/*` calls with backend REST API calls.
- [ ] Regenerate API client from Phase 4.5 backend OpenAPI spec.
- [x] Wire `VITE_API_BASE_URL`.
- [x] Wire real auth/session provider.
- [ ] Normalize encoding artifacts in migrated text.
- [ ] Verify route parity for all current routes in `src/App.tsx`.
- [ ] Verify visual parity for dashboard, assistant, knowledge center, workspace, admin, analytics, and mobile layout.
- [ ] Run typecheck and production build in the integrated repository after migration.

Continuous-indexing UI note: My Workspace upload completion is non-blocking
and explicitly tells the user that processing continues in the background.
Document rows poll the durable status through queued, extraction, chunking,
embedding, indexed, or failed states without freezing the upload surface.

## 16. Complete Files to Migrate

This is the explicit file-by-file migration list for recreating the current frontend in the integrated repository.

### Application root files

- `artifacts/cial-dashboard/.env.example`
- `artifacts/cial-dashboard/components.json`
- `artifacts/cial-dashboard/index.html`
- `artifacts/cial-dashboard/package.json`
- `artifacts/cial-dashboard/tsconfig.json`
- `artifacts/cial-dashboard/vite.config.ts`

### Public assets

- `artifacts/cial-dashboard/public/cial-logo.png`
- `artifacts/cial-dashboard/public/favicon.svg`
- `artifacts/cial-dashboard/public/opengraph.jpg`
- `artifacts/cial-dashboard/public/robots.txt`

### Source files

- `artifacts/cial-dashboard/src/App.tsx`
- `artifacts/cial-dashboard/src/components/assistant/AssistantSettingsPopover.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ChatControlBar.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ChatMessage.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ChatPanel.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ContextChips.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ContextManagerDialog.tsx`
- `artifacts/cial-dashboard/src/components/assistant/ConversationHistory.tsx`
- `artifacts/cial-dashboard/src/components/assistant/RetrievalTimeline.tsx`
- `artifacts/cial-dashboard/src/components/assistant/SourceCitationCard.tsx`
- `artifacts/cial-dashboard/src/components/assistant/SourceViewerPanel.tsx`
- `artifacts/cial-dashboard/src/components/common/AnnouncementCard.tsx`
- `artifacts/cial-dashboard/src/components/common/ChartCard.tsx`
- `artifacts/cial-dashboard/src/components/common/DashboardBlock.tsx`
- `artifacts/cial-dashboard/src/components/common/DataTable.tsx`
- `artifacts/cial-dashboard/src/components/common/EmptyState.tsx`
- `artifacts/cial-dashboard/src/components/common/FilterBar.tsx`
- `artifacts/cial-dashboard/src/components/common/PageHeader.tsx`
- `artifacts/cial-dashboard/src/components/common/QuickActionCard.tsx`
- `artifacts/cial-dashboard/src/components/common/SearchBar.tsx`
- `artifacts/cial-dashboard/src/components/common/StatCard.tsx`
- `artifacts/cial-dashboard/src/components/common/StatusPill.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/HeroSearch.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/KpiRow.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/AIConversationsBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/AnnouncementsBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/ExpertSpotlightBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/KnowledgeGapsBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/PopularSearchesBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/QuickAccessBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/RecentDocumentsBlock.tsx`
- `artifacts/cial-dashboard/src/components/dashboard/blocks/TopContributorsBlock.tsx`
- `artifacts/cial-dashboard/src/components/documents/DocumentCard.tsx`
- `artifacts/cial-dashboard/src/components/documents/DocumentRow.tsx`
- `artifacts/cial-dashboard/src/components/documents/UploadModal.tsx`
- `artifacts/cial-dashboard/src/components/knowledge-center/KnowledgeCenter.tsx`
- `artifacts/cial-dashboard/src/components/layout/AppShell.tsx`
- `artifacts/cial-dashboard/src/components/layout/MobileSidebarDrawer.tsx`
- `artifacts/cial-dashboard/src/components/layout/Sidebar.tsx`
- `artifacts/cial-dashboard/src/components/layout/TopBar.tsx`
- `artifacts/cial-dashboard/src/components/ui/accordion.tsx`
- `artifacts/cial-dashboard/src/components/ui/alert-dialog.tsx`
- `artifacts/cial-dashboard/src/components/ui/alert.tsx`
- `artifacts/cial-dashboard/src/components/ui/aspect-ratio.tsx`
- `artifacts/cial-dashboard/src/components/ui/avatar.tsx`
- `artifacts/cial-dashboard/src/components/ui/badge.tsx`
- `artifacts/cial-dashboard/src/components/ui/breadcrumb.tsx`
- `artifacts/cial-dashboard/src/components/ui/button-group.tsx`
- `artifacts/cial-dashboard/src/components/ui/button.tsx`
- `artifacts/cial-dashboard/src/components/ui/calendar.tsx`
- `artifacts/cial-dashboard/src/components/ui/card.tsx`
- `artifacts/cial-dashboard/src/components/ui/carousel.tsx`
- `artifacts/cial-dashboard/src/components/ui/chart.tsx`
- `artifacts/cial-dashboard/src/components/ui/checkbox.tsx`
- `artifacts/cial-dashboard/src/components/ui/collapsible.tsx`
- `artifacts/cial-dashboard/src/components/ui/command.tsx`
- `artifacts/cial-dashboard/src/components/ui/context-menu.tsx`
- `artifacts/cial-dashboard/src/components/ui/dialog.tsx`
- `artifacts/cial-dashboard/src/components/ui/drawer.tsx`
- `artifacts/cial-dashboard/src/components/ui/dropdown-menu.tsx`
- `artifacts/cial-dashboard/src/components/ui/empty.tsx`
- `artifacts/cial-dashboard/src/components/ui/field.tsx`
- `artifacts/cial-dashboard/src/components/ui/form.tsx`
- `artifacts/cial-dashboard/src/components/ui/hover-card.tsx`
- `artifacts/cial-dashboard/src/components/ui/input-group.tsx`
- `artifacts/cial-dashboard/src/components/ui/input-otp.tsx`
- `artifacts/cial-dashboard/src/components/ui/input.tsx`
- `artifacts/cial-dashboard/src/components/ui/item.tsx`
- `artifacts/cial-dashboard/src/components/ui/kbd.tsx`
- `artifacts/cial-dashboard/src/components/ui/label.tsx`
- `artifacts/cial-dashboard/src/components/ui/menubar.tsx`
- `artifacts/cial-dashboard/src/components/ui/navigation-menu.tsx`
- `artifacts/cial-dashboard/src/components/ui/pagination.tsx`
- `artifacts/cial-dashboard/src/components/ui/popover.tsx`
- `artifacts/cial-dashboard/src/components/ui/progress.tsx`
- `artifacts/cial-dashboard/src/components/ui/radio-group.tsx`
- `artifacts/cial-dashboard/src/components/ui/resizable.tsx`
- `artifacts/cial-dashboard/src/components/ui/scroll-area.tsx`
- `artifacts/cial-dashboard/src/components/ui/select.tsx`
- `artifacts/cial-dashboard/src/components/ui/separator.tsx`
- `artifacts/cial-dashboard/src/components/ui/sheet.tsx`
- `artifacts/cial-dashboard/src/components/ui/sidebar.tsx`
- `artifacts/cial-dashboard/src/components/ui/skeleton.tsx`
- `artifacts/cial-dashboard/src/components/ui/slider.tsx`
- `artifacts/cial-dashboard/src/components/ui/sonner.tsx`
- `artifacts/cial-dashboard/src/components/ui/spinner.tsx`
- `artifacts/cial-dashboard/src/components/ui/switch.tsx`
- `artifacts/cial-dashboard/src/components/ui/table.tsx`
- `artifacts/cial-dashboard/src/components/ui/tabs.tsx`
- `artifacts/cial-dashboard/src/components/ui/textarea.tsx`
- `artifacts/cial-dashboard/src/components/ui/toast.tsx`
- `artifacts/cial-dashboard/src/components/ui/toaster.tsx`
- `artifacts/cial-dashboard/src/components/ui/toggle-group.tsx`
- `artifacts/cial-dashboard/src/components/ui/toggle.tsx`
- `artifacts/cial-dashboard/src/components/ui/tooltip.tsx`
- `artifacts/cial-dashboard/src/components/workspace/AISearchModeSelector.tsx`
- `artifacts/cial-dashboard/src/components/workspace/CollectionCard.tsx`
- `artifacts/cial-dashboard/src/components/workspace/PersonalStorageCard.tsx`
- `artifacts/cial-dashboard/src/components/workspace/PrivacyBadge.tsx`
- `artifacts/cial-dashboard/src/components/workspace/RecentAIChats.tsx`
- `artifacts/cial-dashboard/src/components/workspace/RecentActivityCard.tsx`
- `artifacts/cial-dashboard/src/components/workspace/RecentUploadsTable.tsx`
- `artifacts/cial-dashboard/src/components/workspace/StorageBreakdownChart.tsx`
- `artifacts/cial-dashboard/src/components/workspace/StorageRing.tsx`
- `artifacts/cial-dashboard/src/components/workspace/WorkspaceStatCard.tsx`
- `artifacts/cial-dashboard/src/components/workspace/WorkspaceUploadButton.tsx`
- `artifacts/cial-dashboard/src/config/appConfig.ts`
- `artifacts/cial-dashboard/src/config/dashboardConfig.ts`
- `artifacts/cial-dashboard/src/config/navigationConfig.ts`
- `artifacts/cial-dashboard/src/config/securityConfig.ts`
- `artifacts/cial-dashboard/src/config/themeConfig.ts`
- `artifacts/cial-dashboard/src/config/userConfig.ts`
- `artifacts/cial-dashboard/src/data/adminData.ts`
- `artifacts/cial-dashboard/src/data/analyticsData.ts`
- `artifacts/cial-dashboard/src/data/assistantData.ts`
- `artifacts/cial-dashboard/src/data/auditLogData.ts`
- `artifacts/cial-dashboard/src/data/dashboardData.ts`
- `artifacts/cial-dashboard/src/data/departmentsData.ts`
- `artifacts/cial-dashboard/src/data/documentsData.ts`
- `artifacts/cial-dashboard/src/data/expertData.ts`
- `artifacts/cial-dashboard/src/data/faqData.ts`
- `artifacts/cial-dashboard/src/data/homePageData.ts`
- `artifacts/cial-dashboard/src/data/knowledgeBaseData.ts`
- `artifacts/cial-dashboard/src/data/knowledgeCenterData.ts`
- `artifacts/cial-dashboard/src/data/knowledgeDriveData.ts`
- `artifacts/cial-dashboard/src/data/knowledgeGapsData.ts`
- `artifacts/cial-dashboard/src/data/knowledgeGraphData.ts`
- `artifacts/cial-dashboard/src/data/learningData.ts`
- `artifacts/cial-dashboard/src/data/quickAnswersData.ts`
- `artifacts/cial-dashboard/src/data/sopData.ts`
- `artifacts/cial-dashboard/src/data/workspace/storageUtils.ts`
- `artifacts/cial-dashboard/src/data/workspace/workspaceData.ts`
- `artifacts/cial-dashboard/src/data/workspace/workspacePermissions.ts`
- `artifacts/cial-dashboard/src/data/workspace/workspaceTypes.ts`
- `artifacts/cial-dashboard/src/hooks/use-mobile.tsx`
- `artifacts/cial-dashboard/src/hooks/use-toast.ts`
- `artifacts/cial-dashboard/src/index.css`
- `artifacts/cial-dashboard/src/lib/utils.ts`
- `artifacts/cial-dashboard/src/main.tsx`
- `artifacts/cial-dashboard/src/pages/AIAssistantPage.tsx`
- `artifacts/cial-dashboard/src/pages/AdminSettingsPage.tsx`
- `artifacts/cial-dashboard/src/pages/AnalyticsPage.tsx`
- `artifacts/cial-dashboard/src/pages/DashboardPage.tsx`
- `artifacts/cial-dashboard/src/pages/DepartmentsPage.tsx`
- `artifacts/cial-dashboard/src/pages/DocumentsPage.tsx`
- `artifacts/cial-dashboard/src/pages/ExpertDirectoryPage.tsx`
- `artifacts/cial-dashboard/src/pages/FAQsPage.tsx`
- `artifacts/cial-dashboard/src/pages/KnowledgeBasePage.tsx`
- `artifacts/cial-dashboard/src/pages/KnowledgeCenterPage.tsx`
- `artifacts/cial-dashboard/src/pages/KnowledgeGapsPage.tsx`
- `artifacts/cial-dashboard/src/pages/KnowledgeGraphPage.tsx`
- `artifacts/cial-dashboard/src/pages/LearningHubPage.tsx`
- `artifacts/cial-dashboard/src/pages/PoliciesSOPsPage.tsx`
- `artifacts/cial-dashboard/src/pages/WorkspacePage.tsx`
- `artifacts/cial-dashboard/src/pages/not-found.tsx`
- `artifacts/cial-dashboard/src/types.ts`
- `artifacts/cial-dashboard/src/types/assistant.ts`
- `artifacts/cial-dashboard/src/types/index.ts`

### Recommended design documentation to migrate

- `docs/design/ANIMATION_GUIDELINES.md`
- `docs/design/COMPONENT_LIBRARY.md`
- `docs/design/DESIGN_LANGUAGE.md`
- `docs/design/ICONOGRAPHY.md`
- `docs/design/PAGE_PATTERNS.md`
- `docs/design/UX_PRINCIPLES.md`

### Optional API/reference files for integration

- `lib/api-client-react/package.json`
- `lib/api-client-react/src/custom-fetch.ts`
- `lib/api-client-react/src/generated/api.schemas.ts`
- `lib/api-client-react/src/generated/api.ts`
- `lib/api-client-react/src/index.ts`
- `lib/api-client-react/tsconfig.json`
- `lib/api-spec/openapi.yaml`
- `lib/api-spec/orval.config.ts`
- `lib/api-spec/package.json`

## 17. Where to Place Section 16 Files in the Integrated Structure

Use this base mapping:

```text
artifacts/cial-dashboard/
-> frontend/
```

That means every file from `artifacts/cial-dashboard` keeps the same relative path after removing the `artifacts/cial-dashboard/` prefix.

Examples:

```text
artifacts/cial-dashboard/index.html
-> frontend/index.html

artifacts/cial-dashboard/package.json
-> frontend/package.json

artifacts/cial-dashboard/public/cial-logo.png
-> frontend/public/cial-logo.png

artifacts/cial-dashboard/src/App.tsx
-> frontend/src/App.tsx

artifacts/cial-dashboard/src/components/ui/button.tsx
-> frontend/src/components/ui/button.tsx

artifacts/cial-dashboard/src/pages/DashboardPage.tsx
-> frontend/src/pages/DashboardPage.tsx
```

### Recommended placement map

| Source path pattern | Target path pattern | Notes |
|---|---|---|
| `artifacts/cial-dashboard/index.html` | `frontend/index.html` | Vite HTML entrypoint. |
| `artifacts/cial-dashboard/package.json` | `frontend/package.json` | Clean Replit-only dependencies before production use. |
| `artifacts/cial-dashboard/vite.config.ts` | `frontend/vite.config.ts` | Remove Replit plugins during integration. |
| `artifacts/cial-dashboard/tsconfig.json` | `frontend/tsconfig.json` | Adjust workspace references if needed. |
| `artifacts/cial-dashboard/components.json` | `frontend/components.json` | Keep shadcn aliases aligned with `src`. |
| `artifacts/cial-dashboard/.env.example` | `frontend/.env.example` | Keep as frontend environment contract. |
| `artifacts/cial-dashboard/public/*` | `frontend/public/*` | Runtime public assets. |
| `artifacts/cial-dashboard/src/main.tsx` | `frontend/src/main.tsx` | React entrypoint. |
| `artifacts/cial-dashboard/src/App.tsx` | `frontend/src/App.tsx` | Route/provider root. |
| `artifacts/cial-dashboard/src/index.css` | `frontend/src/index.css` | Tailwind v4 and design token source. |
| `artifacts/cial-dashboard/src/components/*` | `frontend/src/components/*` | Preserve component folder structure. |
| `artifacts/cial-dashboard/src/config/*` | `frontend/src/config/*` | Preserve non-auth UI config; auth now comes from the backend session provider. |
| `artifacts/cial-dashboard/src/hooks/*` | `frontend/src/hooks/*` | Preserve hook paths. |
| `artifacts/cial-dashboard/src/lib/*` | `frontend/src/lib/*` | Preserve utility paths. |
| `artifacts/cial-dashboard/src/pages/*` | `frontend/src/pages/*` | Preserve route page paths. |
| `artifacts/cial-dashboard/src/types*` | `frontend/src/types*` | Preserve shared type paths. |
| `artifacts/cial-dashboard/src/types/*` | `frontend/src/types/*` | Preserve shared type paths. |

### Mock data placement

There are two valid approaches for `src/data/*`.

For a zero-code-change migration first, keep the current paths:

```text
artifacts/cial-dashboard/src/data/dashboardData.ts
-> frontend/src/data/dashboardData.ts

artifacts/cial-dashboard/src/data/workspace/workspaceData.ts
-> frontend/src/data/workspace/workspaceData.ts
```

This is the safest first copy because current imports use `@/data/...`.

For a cleaner integrated structure after imports are updated, move mock/static data under `src/data/mock`:

```text
artifacts/cial-dashboard/src/data/dashboardData.ts
-> frontend/src/data/mock/dashboardData.ts

artifacts/cial-dashboard/src/data/workspace/workspaceData.ts
-> frontend/src/data/mock/workspace/workspaceData.ts
```

If using `frontend/src/data/mock`, update imports from:

```text
@/data/dashboardData
@/data/workspace/workspaceData
```

to:

```text
@/data/mock/dashboardData
@/data/mock/workspace/workspaceData
```

### Design documentation placement

Move design docs into the frontend documentation folder:

```text
docs/design/DESIGN_LANGUAGE.md
-> frontend/docs/design/DESIGN_LANGUAGE.md

docs/design/COMPONENT_LIBRARY.md
-> frontend/docs/design/COMPONENT_LIBRARY.md
```

Apply the same mapping for all files in `docs/design`.

### Optional API/reference placement

Do not copy the old API client into `src` unless the integrated frontend will reuse the current generated client temporarily.

If reused, place it like this:

```text
lib/api-client-react/src/custom-fetch.ts
-> frontend/src/api/custom-fetch.ts

lib/api-client-react/src/generated/api.ts
-> frontend/src/api/generated/api.ts

lib/api-client-react/src/generated/api.schemas.ts
-> frontend/src/api/generated/api.schemas.ts

lib/api-spec/openapi.yaml
-> frontend/src/api/openapi.yaml
```

Recommended long-term structure:

```text
frontend/src/api/
  client.ts
  generated/
    api.ts
    api.schemas.ts
  adapters/
```

`frontend/src/api/client.ts` should configure base URL, auth/session behavior, generated client access, and shared error handling for the integrated backend.

### AI Assistant health and submission contract

The integrated assistant owns `AssistantSystemHealth.tsx`,
`useSystemStatus.ts`, and the typed `/api/system/status` client contract. The
header indicator must preserve the four labels System ready, Updating
knowledge, Degraded, and Unavailable, adaptive polling, and the expandable
generation/queue/worker/GPU/model detail view.

The composer must preserve the single Enter/Send path, immediate authenticated
status preflight, blue-state submission, request cancellation, terminal Retry,
and draft-clearing boundary: text is cleared only from the stream's successful
connection callback, never before fetch initiation succeeds.

The retrieval timeline consumes backend stage events and maps Connected,
Validating request, Loading published generation, Searching knowledge,
Reranking sources, Generating answer, Completed, and Failed. Its optional
details are limited to duration, candidate count, and safe error state. Stream
errors surface `failed_stage`, `reason`, and `timeout_state`; a completed
partial answer keeps Retry visible and explains which retrieval stage degraded.

### Admin AI Operations Console contract

The integrated frontend must retain these production files:

- `src/pages/AdminSystemMonitorPage.tsx`
- `src/pages/AdminAccessDeniedPage.tsx`
- `src/hooks/useAdminSystemMonitor.ts`
- the `AdminSystemMonitor` and `OperationsEvent` API types;
- the `/api/admin/system/monitor` snapshot and
  `/api/admin/system/stream` SSE client functions; and
- the permission-filtered System Monitor navigation entry.

`/admin/system-monitor` must be declared before the generic `/admin/:sub`
route. Client access checks use the authenticated `permission_names` array and
accept only `monitor_system` or `manage_settings`; the backend repeats the
authorization and is authoritative. Normal users must not receive the
navigation entry or initialize the monitor hook.

The monitor is backend-driven. Its query panel includes active request count,
the current stage with live elapsed time, latest component latencies, and the
exact failed stage/timeout reason. Do not migrate mock metrics, random chart data,
or simulated service states into this route. The hook must preserve
credentialed SSE, snapshot preflight, bounded reconnect, authentication-failure
state, and seven-second stale detection. The console must preserve the CIAL
green enterprise visual language, reduced visual motion, and explicit
unavailable values when a telemetry source has no sample.

### Files not to place anywhere

Do not copy these into the integrated frontend, even if present under `artifacts/cial-dashboard`:

```text
artifacts/cial-dashboard/dist
artifacts/cial-dashboard/node_modules
artifacts/cial-dashboard/.tsbuildinfo
artifacts/cial-dashboard/.replit-artifact
artifacts/cial-dashboard/dev-server.err.log
artifacts/cial-dashboard/dev-server.out.log
```

These are generated or development-only artifacts. Recreate `dist` with the production build and recreate `node_modules` by installing dependencies from the migrated `package.json` and lockfile strategy.

## Runtime Performance Status Addendum

The live operations console distinguishes configured GPU device from current
indexer model residency. It shows indexer GPU state, active embedding jobs,
chat-priority state, first-token latency, tokens per second, and Ollama
model-load time. Missing driver values remain unavailable.

A stale or stopped indexer is a degraded indexing condition. The Assistant send
gate continues to use backend `chat_available`, so an existing published
generation remains queryable while the worker is stopped or restarting.

## LAN Production Delivery

LAN Server Mode never exposes the Vite development or preview server. Caddy
serves `frontend/dist/public`, applies the SPA fallback and immutable asset
cache policy, and proxies `/api/*` on the same origin. The frontend therefore
keeps relative API URLs and requires no LAN-only CORS or absolute backend
address. Admin System Monitor consumes the additive `lan_access` projection
and displays only sanitized state, URLs, transport, firewall, and discovery
readiness.
