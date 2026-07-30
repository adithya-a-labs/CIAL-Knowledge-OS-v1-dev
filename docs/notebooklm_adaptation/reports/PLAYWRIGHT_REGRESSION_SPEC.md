# Proposed CIAL Playwright regression specification

Do not execute these scenarios as part of this research.

1. **Create notebook**
   - Precondition: authenticated user with notebook permission.
   - Steps: library -> Create.
   - Assert: empty context/chat/output state, route, accessible headings.
2. **Context selection changes grounding**
   - Attach two authorized Corpus documents.
   - Ask identical question with one then both selected.
   - Assert selected IDs in request, citation document IDs within selection,
     no answer-text snapshot, no unauthorized source.
3. **Citation deep link**
   - Click citation; assert detail role/name, document/page/chunk resolver,
     shared viewer highlight fallback, Escape and focus restoration.
4. **Source processing**
   - Assert queued/extracting/embedding/ready and typed failed/retry states.
5. **Notes**
   - Create/edit/close/reload/reopen/delete; assert PostgreSQL persistence,
     separate indexing state, confirmation and focus restoration.
6. **Artifact lifecycle**
   - Parameterize every enabled artifact type.
   - Assert 202 job, progress events, durable card, viewer, menu, cancel/retry,
     error state, permissions, and retention.
7. **Responsive matrix**
   - 1440x900 and 1024x768: three surfaces present.
   - 768x1024 and 390x844: named tabs, one active panel, no horizontal overflow.
   - Repeat context -> chat -> citation -> output navigation.
8. **Accessibility**
   - Named icon buttons, tab semantics, focus order, trap, Escape, restoration,
     reduced motion, disabled states, 40px minimum targets, axe where appropriate.
9. **Persistence and navigation**
   - Reload, browser back to library, exact reopen; assert context, chat,
     citations, notes, artifact jobs, and active panel restoration.
10. **Authorization failure**
    - Remove access between selection and query; assert context removal, 403,
      no cached evidence leak, no broadened fallback.
