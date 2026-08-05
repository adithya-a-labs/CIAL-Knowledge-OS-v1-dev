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

Recommended execution order: 001, then 002–008 in parallel where files do not overlap, followed by integrated Playwright and regression validation.

All plans preserve the existing calm, premium, enterprise design language and prohibit new animation dependencies, `transition-all`, `ease-in`, `scale(0)`, bounce, decorative springs, and high-frequency keyboard animation.
