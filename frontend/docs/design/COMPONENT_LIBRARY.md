# Component Library Standards

This document defines the reusable UI expectations for common components in CIAL Knowledge OS. Components should be consistent with the design language and reusable across pages.

## PrimaryButton
- Purpose: the main call to action for a primary workflow
- Visual rules: clear emphasis, restrained styling, strong contrast, no unnecessary decoration
- Interaction states: default, hover, active, disabled, focus-visible
- Accessibility: sufficient contrast, visible focus, semantic button role
- Where to use: confirm, save, continue, submit, create

## SecondaryButton
- Purpose: supporting actions that are important but not primary
- Visual rules: quieter treatment, still legible, consistent outline or soft fill
- Interaction states: default, hover, active, disabled, focus-visible
- Accessibility: clear labels, keyboard support
- Where to use: cancel, back, export, preview

## GhostButton
- Purpose: low-emphasis actions inside dense UI
- Visual rules: minimal visual weight, subtle hover state, no heavy borders
- Interaction states: default, hover, active, focus-visible
- Accessibility: avoid icon-only variants without labels
- Where to use: inline actions, table row actions, tertiary controls

## IconButton
- Purpose: compact action controls for toolbars, lists, and panels
- Visual rules: clear size, visible hover/active states, consistent icon treatment
- Interaction states: default, hover, pressed, disabled, focus-visible
- Accessibility: aria-label required for icon-only buttons
- Where to use: search, filter, settings, more actions

## SearchInput
- Purpose: fast entry into search and discovery workflows
- Visual rules: compact, calm, visually lightweight, easy to scan
- Interaction states: default, focused, loading, empty, with results
- Accessibility: label or clear accessible name, keyboard support
- Where to use: global search, knowledge search, document search

## FilterSelect
- Purpose: narrow content without heavy UI friction
- Visual rules: compact and consistent, no overly decorative control styling
- Interaction states: default, open, selected, disabled
- Accessibility: keyboard operable, understandable labels
- Where to use: document filters, analytics filters, department filters

## Tabs
- Purpose: switch between related views or modes
- Visual rules: restrained, low-noise, clearly active state
- Interaction states: default, hover, active, disabled
- Accessibility: clear tab semantics and keyboard navigation
- Where to use: content views, analytics views, workspace modes

## Cards
- Purpose: present a distinct object, item, or summary
- Visual rules: clean container, stable spacing, subtle elevation or border, clear content hierarchy
- Interaction states: default, hover, selected, loading
- Accessibility: logical heading structure, keyboard support when interactive
- Where to use: knowledge categories, departments, documents, metrics, modules

## FileManager
- Purpose: browse, select, and act on files and folders
- Visual rules: document-style browsing experience, not spreadsheet-like
- Interaction states: hover, selected, active, empty state, loading
- Accessibility: keyboard selection and action support, clear labels
- Where to use: documents, policies, SOPs, uploads, workspace files

## Breadcrumb
- Purpose: show current location and support navigation back through hierarchy
- Visual rules: compact and unobtrusive, clear separation between steps
- Interaction states: hover, current item emphasis
- Accessibility: use semantic navigation pattern
- Where to use: file browsing, document detail views, settings sections

## Badge
- Purpose: show status, type, ownership, or category quickly
- Visual rules: subtle and consistent, not loud or oversized
- Interaction states: default, selected, muted
- Accessibility: do not rely on color alone
- Where to use: document status, category tags, system labels

## EmptyState
- Purpose: guide users when there is no content yet or no search result
- Visual rules: calm tone, clear explanation, a clear next action when relevant
- Interaction states: static, with action button
- Accessibility: readable text and keyboard-accessible action
- Where to use: empty folders, no search results, no learning content, no analytics yet

## SidebarNav
- Purpose: provide primary product navigation and section entry points
- Visual rules: quiet and structured, strong hierarchy, low visual noise
- Interaction states: default, hover, active, collapsed states
- Accessibility: keyboard navigable, clear active state, descriptive labels
- Where to use: main product navigation

## Topbar
- Purpose: provide global context, search access, and utility actions
- Visual rules: calm and compact, stable across pages, no unnecessary decoration
- Interaction states: responsive, search-focused, action states
- Accessibility: logical order and keyboard support
- Where to use: all major pages
