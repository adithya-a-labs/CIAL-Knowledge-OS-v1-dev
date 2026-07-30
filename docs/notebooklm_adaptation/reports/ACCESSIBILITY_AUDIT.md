# Accessibility audit

## Positive observations

- Narrow panels expose proper tab roles and selected state.
- Source selection exposes named checkboxes and checked state.
- Chat supports keyboard Enter and a named Submit control.
- Dialog viewers expose Back/Share/Close/More controls.
- Mind Map exposes a tree plus arrow-key and Enter instructions.
- Share dialog exposes form controls and disabled state.

## Findings

| ID | Severity | Finding |
|---|---|---|
| a11y-004 | Medium | Analytics enters focus order as `trending_up`. |
| a11y-005 | Medium | Source-preview return left focus on BODY. |
| a11y-006 | Medium | Mind Map Escape close left focus on BODY. |
| a11y-007 | Medium | Escape did not close iframe Quiz; explicit Close did. |

Observed header focus order began Settings -> Create -> Copy -> analytics icon ->
Share -> selected Studio tab -> Audio -> Customise Audio -> Slide deck.
No automated WCAG conformance claim is made.
