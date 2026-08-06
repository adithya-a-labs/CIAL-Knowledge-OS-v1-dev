# 009 — Gate Knowledge Graph hover motion to precise pointers

- **Status**: DONE
- **Commit**: ac21d8e
- **Severity**: MEDIUM
- **Category**: Accessibility and performance
- **Estimated scope**: 4 files, small

## Problem

`frontend/src/pages/KnowledgeGraphPage.tsx:18` stores pointer hover in React state,
and `frontend/src/pages/KnowledgeGraphPage.tsx:107-120` applies an inline scale for
both hover and selection. The transform is property-scoped, but its movement is
not explicitly limited to devices that report both hover and a fine pointer.
Touch users should retain selection through stroke and shadow without node
movement or synthetic hover residue.

## Target

Keep the graph's existing transform-only `160ms` feedback for precise pointers.
Move the scale rule into `src/index.css` under:

```css
@media (hover: hover) and (pointer: fine) { /* scale selected/hovered nodes */ }
```

Use `--motion-duration-short` and `--motion-ease-move`. Touch keeps node
geometry static. Reduced motion continues to suppress the transform duration.
Selection stroke/shadow, click behavior, graph data, layout, and colors remain
unchanged.

## Repo conventions to follow

- Motion tokens live at `frontend/src/index.css:147-153`.
- Targeted reduced-motion handling lives at `frontend/src/index.css:869-905`.
- Existing graph behavior uses transform only at
  `frontend/src/pages/KnowledgeGraphPage.tsx:113-120`.

## Steps

1. Remove React hover state and inline transform calculation from the graph.
2. Add a graph-node class and selected-state data attribute.
3. Gate selected/hover scale behind fine-pointer hover media capabilities.
4. Extend source and Playwright regressions to prove touch geometry stays still.

## Boundaries

- Do not change graph data, SVG layout, selected-state stroke/shadow, routes, or themes.
- Do not add dependencies or motion libraries.
- Do not animate stroke, filter, radius, or layout properties.

## Verification

- **Mechanical**: `pnpm.cmd test`, `pnpm.cmd run typecheck`,
  `pnpm.cmd run verify:motion`, and the production Vite build must pass.
- **Feel check**: repeat hover across graph nodes on desktop; feedback remains
  restrained and responsive. Tap nodes at 390×844 touch emulation; selection is
  visible but computed transform remains `none`.
- **Done when**: fine-pointer hover is the only capability that enables node
  scale, touch selection stays static, and all checks pass.
