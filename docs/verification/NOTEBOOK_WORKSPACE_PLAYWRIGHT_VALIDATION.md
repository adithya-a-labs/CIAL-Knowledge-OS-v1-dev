# Notebook Workspace Playwright Validation

Date: 2026-08-02  
Runtime: authenticated live frontend `127.0.0.1:5173`, live FastAPI/PostgreSQL backend, Playwright MCP only.

No routes, storage, or API state were stubbed. Validation used the existing authenticated test session and a disposable generic text upload. Retained evidence contains no email addresses, tokens, source bodies, or private notebook titles.

| Scenario | Result | Observation |
| --- | --- | --- |
| Library loads after migration | PASS | Empty state recovered from the pre-migration 500 after retry; subsequent fresh navigation was clean. |
| Create notebook | PASS | Created a persisted personal notebook and navigated to its stable UUID route. |
| Rename and reload | PASS | Renamed to `Validation Notebook`; title, three source references, and active count survived a fresh navigation. |
| My Workspace folder navigation | PASS | Root and nested personal folders loaded through real APIs. |
| Knowledge Center search/attach | PASS | Attached authorized indexed enterprise references; duplicates were disabled. |
| Governed upload | PASS | Synthetic TXT entered the existing upload queue, attached immediately, stayed inactive, and showed `indexing`. |
| Active subset | PASS | Attached count and active count changed independently; chat context count matched ready active references. |
| Chat transport/history | PASS | Bound ordinary session accepted the request, showed request stage/timer, completed, and remained in notebook history. |
| Grounded answer and citations | BLOCKED | Selected legacy corpus item returned 0 chunks; the database record had no extracted text. |
| Two concurrent grounded questions | BLOCKED | A second meaningful grounded run would not validate concurrency while the chosen data produced no evidence; concurrency remains covered by existing multi-request suites. |
| Source preview | PASS | Existing viewer opened the authorized disposable source. |
| Escape/focus return | PASS | A discovered mobile overlay defect was fixed; Escape now closes the viewer and returns focus to its source trigger. |
| Studio generate/save/export | BLOCKED | Existing summary service correctly returned 422 because the active legacy corpus record had no extracted text. |
| Notes tab reuse | PASS | Existing Notes workspace is mounted as the notebook Notes surface; destructive note mutation was not performed in this retained-data session. |
| Unauthorized second user | NOT RUN | No approved secondary authenticated browser identity was available. Owner isolation is covered by backend contract tests. |
| Mobile tabs and overflow | PASS | 390x844 Sources/Chat/Studio/Notes tabs rendered; document width equaled viewport width. |
| Theme switching | PASS | Dark applied `html.dark` and persisted `dark`; System was restored. |
| Console after fresh navigation | PASS | Current-session console log retained in evidence; earlier 500 was pre-migration and two later 422s are the documented empty-extraction finding. |
| Playwright trace | NOT RUN | The available Playwright MCP exposes snapshots, screenshots, console, and network capture but no trace start/stop capability. |

## Evidence

- `outputs/playwright/notebook-workspace/library-persistence-1440.png`
- `outputs/playwright/notebook-workspace/workspace-1440.png`
- `outputs/playwright/notebook-workspace/workspace-mobile-390.png`
- `outputs/playwright/notebook-workspace/accessibility-mobile.md`
- `outputs/playwright/notebook-workspace/console-current.log`
- `outputs/playwright/notebook-workspace/network-notebooks.log`
- `outputs/playwright/notebook-workspace/validation-source.txt`

The evidence folder is intentionally excluded from version control by the repository output policy.

