# CIAL Motion Implementation Plans

Commit baseline: `51edafa`

| Plan | Title | Severity | Status | Dependencies |
| --- | --- | --- | --- | --- |
| 001 | Motion foundation and reduced motion | MEDIUM | DONE | None |
| 002 | Assistant auto-follow | HIGH | DONE | 001 |
| 003 | Assistant resize | HIGH | DONE | 001 |
| 004 | Assistant lifecycles | HIGH | DONE | 001 |
| 005 | Appearance control | MEDIUM | DONE | 001 |
| 006 | Graph and FAQ cleanup | MEDIUM | DONE | 001 |
| 007 | Document workspace overlays | MEDIUM | DONE | 001 |
| 008 | Source accordion | MEDIUM | DONE | 001 |
| 009 | Gate Knowledge Graph hover motion to precise pointers | MEDIUM | DONE | 001, 006 |

Recommended execution order: 001, then 002–008 in parallel where files do not overlap, followed by integrated Playwright and regression validation.

All plans preserve the existing calm, premium, enterprise design language and prohibit new animation dependencies, `transition-all`, `ease-in`, `scale(0)`, bounce, decorative springs, and high-frequency keyboard animation.

## 2026-08-06 primitive follow-up

The completed plans were re-audited against the live application. A narrow
shared-primitive follow-up removed the remaining `transition-all` utilities,
standardized Sheet, tooltip, tab, progress, navigation, OTP, accordion, and
welcome timings on the existing tokens, removed generic non-interactive card
lift, restored the progress primitive's accessible value, and expanded the
motion source contract to `src/components/ui` and dashboard components. No new
plan or dependency was required because the existing Radix/CSS architecture
covered every confirmed primitive issue.

## 2026-08-06 reconciliation traceability

Reconciled against commit `ac21d8e`, the current working diff, plans 001–009,
source tests, and the integrated Playwright verifiers.

| Original item | Classification | Source evidence | Verification evidence |
| --- | --- | --- | --- |
| Assistant repeated smooth scrolling | Already implemented | `ChatPanel.tsx:185-189, 666-670` | Assistant motion source test; motion verifier manual override/resume checks |
| Assistant resize geometry transitions | Already implemented | `ChatPanel.tsx:855-886`; `ChatMessage.tsx:350-370` | Direct-pointer resize Playwright check |
| Assistant conditional panel lifecycle | Already implemented | `useReversiblePresence.ts:4-42`; `AIAssistantPage.tsx:127-195` | Desktop/mobile rapid reversal and focus checks |
| Reduced-motion universal clamp | Already implemented | `index.css:869-905` | Reduced drawer and Appearance checks |
| Appearance-control timing | Already implemented | `index.css:451-527` | 23-check Appearance verifier plus motion timing check |
| Knowledge Graph hover performance | Partial → implemented by plan 009 | `KnowledgeGraphPage.tsx:103-117`; `index.css:837-843` | Repeated desktop hover plus touch-static Playwright checks |
| Shared motion tokens | Already implemented | `index.css:147-153` | Motion foundation source contract |
| FAQ false container interaction | Already implemented | `FAQsPage.tsx:110-143` | Static article Playwright check |
| Mobile History drawer | Already implemented | `AIAssistantPage.tsx:157-195` | Open/close/reversal/Escape/route cleanup checks |
| Document Workspace overlays | Already implemented | `DocumentWorkspacePage.tsx:356-357, 460-461` | Touch iPad lifecycle/rotation/cleanup suite |
| Source Citation accordion | Already implemented | `SourceCitationCard.tsx:90-131` | Variable-content and rapid-reversal checks |

No reconciliation plan remains TODO. The only partial item was the explicit
fine-pointer gate completed in plan 009; no new dependency was required.
