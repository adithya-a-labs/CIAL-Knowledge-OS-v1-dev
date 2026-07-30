# Multi-request chat verification

Verified: 2026-07-30  
Scope: bounded process-local FastAPI chat concurrency and independent React
request state.

## Outcome

The implementation supports multiple live chat requests without restoring the
previous global query lock or frontend single-flight guard. Admission,
scheduling, scarce-resource use, event buffering, cancellation, persistence
order, and shutdown are bounded. Mutable query configuration, callbacks,
filters, caches, token buffers, abort controllers, errors, and results are
request-local.

This remains a live-stream architecture. Browser reload, network disconnect,
auth invalidation, panel unmount, backend restart, or explicit Stop cancels
in-flight work; no durable in-flight resume was added. Completed PostgreSQL
history remains authoritative.

## Browser checklist

| Scenario | Result | Evidence |
| --- | --- | --- |
| Two overlapping submissions | PASS | Two concurrent `POST /api/chat/stream` requests with distinct client/server request IDs |
| Same draft materializes one session | PASS | Both request bodies use session `2016926a-c02e-441f-93e2-b01b39ecd275` |
| Out-of-order completion | PASS | SECOND-FAST result at 781 ms; FIRST-SLOW result at 2,875 ms |
| Submission-order rendering | PASS | FIRST user/assistant pair remains before SECOND pair after both complete |
| Composer remains available | PASS | Second request was submitted while the first was running |
| Frontend independent cancellation | PASS | Target request transitioned to `Stopped`; neighboring request stayed completed and retained its own answer/actions |
| Request-specific controls | PASS | Live Stop control was labelled with its client request ID |
| Cancellation console | PASS | No runtime error in the cancellation-page console log |
| Network/request isolation | PASS | Separate bodies and NDJSON streams preserve matching client/server IDs |
| Desktop layout | PASS | 1350x735 full-page snapshot and screenshot |
| Light/System/Dark browser toggle | SKIPPED | The one permitted final Vite restart failed because Windows `Start-Process` split a spaced entry path; deterministic theme tests passed |
| Narrow responsive browser resize | SKIPPED | Same bounded Vite-process limitation; deterministic mobile-containment/navigation tests passed |

The cancellation browser result is recorded as
**PASS frontend independent cancellation**. Server behavior is not inferred
from the timing-sensitive browser disconnect.

## Server cooperative cancellation

`test_cooperative_generation_cancellation_is_request_local_and_skips_persistence`
uses `threading.Event` barriers and the production controller/resource gate.
It proves:

1. request A enters generation and emits one token;
2. request B enters independently;
3. cancelling A sets A's event but not B's;
4. A's controlled generation iterator closes and emits no token after cancel;
5. A never reaches its persistence checkpoint;
6. A releases its generation slot;
7. B remains uncancelled, reaches persistence, and completes;
8. active/queued counts, generation use, and generation waiters return to zero,
   with one cancellation and one completion recorded.

This is recorded as **PASS server cooperative cancellation**. Browser
reload/network-disconnect cancellation remains governed by the existing live
stream contract and was not promoted to durable recovery.

## Browser artifacts

Artifacts are under `outputs/playwright/multi-request-chat/`:

- `desktop-overlap-complete.png`
- `desktop-overlap-snapshot.md`
- `first-request-body.json`
- `second-request-body.json`
- `first-response.ndjson`
- `second-response.ndjson`
- `overlap-network.md`
- `execution-trace.md`
- `overlap-console.log`
- `cancellation-snapshot.yml`
- `cancellation-console.log`
- `results.json`

The two late `system/status` errors in `overlap-console.log` occurred after the
fixture was intentionally stopped, more than 85 seconds after the verified
chat scenario. The cancellation page itself logged only the React development
tools notice.

The browser fixture is a deterministic FastAPI app using the production
`ChatConcurrencyController`; it does not exercise PostgreSQL, Qdrant, or
Ollama. A separate real backend startup reached local Qdrant and Ollama, but
reported no configured metadata database/published generation, so no real-model
end-to-end latency or correctness claim is made.

## Automated verification

Final targeted commands:

```text
python -m pytest \
  tests/test_chat_multi_request_concurrency.py \
  tests/test_chat_request_isolation.py \
  tests/test_gpu_runtime_management.py \
  tests/test_chat_action_contract.py \
  tests/test_explain_simpler.py \
  tests/test_create_checklist.py \
  tests/test_chat_history_persistence.py \
  tests/test_admin_system_monitor.py -q
```

Result: 75 passed. This includes all 13 controller tests after the final
fair-scheduling and slow-consumer preservation audit, the deterministic
cooperative-cancellation proof, request-state isolation, GPU lease ownership,
derived-message ordering, history persistence, and admin metrics.

```text
node --test
```

Result: 85 passed. This includes request-specific concurrency, cancellation,
message order, draft materialization, auth cleanup, mobile containment, global
responsive navigation, Light/System/Dark contracts, composer preservation on
capacity rejection, accurate terminal-outcome logging, and cancellation of a
pending animation-frame token flush before the terminal `Stopped` update.

```text
pnpm.cmd run typecheck
pnpm.cmd exec vite build --outDir .validation-dist-final
```

Result: typecheck passed; production build passed with 3,166 modules. Existing
sourcemap and large-chunk warnings remain. The isolated output directory was
used because the normal `dist` CSS artifact was locked by an unrelated live
process.

The complete backend suite was run before the final documentation/config audit:
541 tests and 50 subtests passed. It was not rerun after the final focused
controller, ordering, and UI-observability changes; the directly affected
75-test backend selection and 85-test frontend suite passed as required by the
bounded closure plan.

Migration verification:

- `alembic heads` returned `20260729_0018 (head)`;
- offline SQL for `20260725_0017:20260729_0018` rendered two additive columns
  and the session/turn/role index successfully;
- no database reset or destructive migration command was used.

## Synthetic capacity probe

`scripts/probe_chat_concurrency.py` exercised 1/2/4/8/16 submissions across
1/2/4/8 users. Results are in
`outputs/performance/multi-request-chat-controller.json`.

Observed controller invariants:

- active global peak never exceeded 8;
- per-user active peak never exceeded 2;
- generation peak remained 1;
- event-channel high-water mark remained 7 against capacity 32;
- cancellation cleaned the waiter without entering generation;
- the 16-request single-user burst produced safe per-user rejections while
  multi-user cases progressed.

This probe is explicitly synthetic. It does not claim real Qdrant/Ollama
latency, database connection usage, GPU/LAN behavior, or production throughput.

## Known limits

- Scheduling and fairness are process-local; no cross-Uvicorn-worker or
  distributed queue was added.
- Active requests are cooperatively cancellable; Python cannot forcibly stop a
  non-cooperative third-party call already executing.
- In-flight streams are not durable and do not resume after reload or restart.
- Browser theme and narrow-viewport reruns were boundedly skipped after the
  permitted Vite restart failed; deterministic UI tests cover those contracts.
- No unverified real-device, LAN, real-model throughput, or database-pool claim
  is made.
