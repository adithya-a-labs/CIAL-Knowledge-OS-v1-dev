# CIAL Knowledge OS Latency Regression Analysis

**Investigation date:** 2026-07-25  
**Repository revision reviewed:** `2e00593` (`main`)  
**Scope:** Read-only investigation of the current chat, retrieval, generation, Ollama, continuous-indexing, frontend-streaming, and telemetry paths. No runtime configuration was changed and no fix was implemented.

# Executive Summary

CIAL Knowledge OS has regressed from reported response times of approximately 10–20 seconds to 90–120+ seconds for the same or similar questions. Some requests now terminate with:

```text
phase4_generation_attempt_failed
TimeoutError: Answer generation exceeded the configured time limit.
```

The available evidence localizes the observed terminal failure to **generation**, specifically the Phase 4 Ollama streaming call. Validation succeeds, the access boundary succeeds, a committed index generation is loaded, and retrieval completes before the timeout. The previously identified retrieval hang was a separate defect: chat entered the batch `run()` lifecycle, which loaded source material and embedded a snapshot before reaching retrieval. The current service instead calls the query-only `answer()` path. That correction removes the earlier pre-retrieval hang but does not explain the remaining generation timeout.

The most likely bottleneck is therefore **Ollama inference or the infrastructure available to Ollama during inference**, not the logical retrieval pipeline. Confidence in that subsystem localization is **high**. Confidence in any one physical root cause is only **medium**, because the current production telemetry does not capture Ollama model-load duration, time to first token, prompt-evaluation duration, output token count, tokens per second, Ollama processor placement, or GPU/VRAM state during the generation interval.

The strongest code-backed hypotheses are:

1. **GPU/VRAM contention between continuous indexing and Ollama.** Chat is logically isolated from indexing, but the standalone indexer can perform BGE-M3 embedding on the GPU while Ollama serves `gemma3:12b`. There is no cross-process GPU admission or inference-priority boundary in the reviewed code. Logical isolation therefore does not guarantee physical resource isolation.
2. **Cold model load or model eviction.** The chat LLM is created lazily on the first question. No explicit Ollama `keep_alive` value is set. The application verifies model installation but does not preload the model into an Ollama runner or measure its load duration.
3. **A larger or insufficiently bounded generation workload.** The standard profile instructs the model to produce at least 250 words and as many as 700 words, while detailed profiles allow up to 2,000 words and some profiles have no maximum. These are prompt instructions, not an Ollama `num_predict` limit. The request also omits an explicit `num_ctx`. Context is bounded in application code, but the exact final prompt size is not exposed by live chat telemetry.
4. **GPU fallback or partial offload.** The system records the indexer embedding device, not Ollama's actual processor split. It is therefore unknown whether `gemma3:12b` is fully GPU-resident, partially offloaded, or CPU-bound during the slow requests.

The recent continuous-indexing and observability changes did **not** modify the Phase 4 generation prompt, evidence-token budget, context-token limit, or response-profile defaults in the reviewed change range. They added hard timeouts, stage telemetry, unconditional use of the LLM streaming interface, query isolation, and concurrent standalone indexing. Consequently, an increased prompt is possible on particular requests or because the newly published corpus selects different evidence, but a static prompt/configuration increase is not demonstrated by the recent diff.

**Classification:** generation/infrastructure bottleneck; retrieval regression is currently unlikely.  
**Subsystem confidence:** high.  
**Specific root-cause confidence:** medium pending runtime measurements.

# Before vs After Architecture Comparison

## Before

```text
question
  -> retrieval
  -> generation
  -> response
```

The earlier shape had fewer visible control-plane stages. It also predated the current production boundary around committed generations and the full Phase 4 retrieval trace. The reported baseline was 10–20 seconds.

## After

```text
question
  -> request validation
  -> access-control resolution
  -> published-generation discovery/use
  -> dense + BM25 retrieval
  -> reciprocal-rank fusion
  -> cross-encoder reranking
  -> evidence selection
  -> token-aware context construction
  -> Phase 4 prompt construction
  -> Ollama streaming generation
  -> citation linking and persistence
  -> response
```

## Potential latency additions

| Addition | What it adds | Expected impact from current design | Regression relevance |
|---|---|---:|---|
| Validation and access control | Request/profile validation, selected-scope resolution, accessible-path lookup | Target below 100 ms for permission validation | It completes successfully in the supplied evidence; actual duration is still needed. |
| Published-generation handling | Uses the already-loaded committed Qdrant/BM25 generation and starts discovery asynchronously | Near-zero on the request path | Unlikely to explain 90–120 seconds unless implementation departed from the reviewed path. |
| Hybrid retrieval | Dense and BM25 branches, normally in parallel | Retrieval before generation target below 3 seconds | Supplied evidence says retrieval completes. |
| RRF fusion | Combines dense/BM25 ranks | Target below 200 ms | Bounded and observed before generation. |
| Cross-encoder reranking | Scores up to a bounded candidate set | Target below 2 seconds; hard ceiling 15 seconds | Adds latency, but cannot by itself explain a generation-stage 120-second timeout. |
| Evidence selection/context fitting | Selects up to eight chunks, targets 800–1,500 evidence tokens, allows 2,400, final context ceiling 4,096 | Expected sub-second to low seconds | Can indirectly increase generation prefill if final context is larger than before. Exact live values are not surfaced. |
| Detailed Phase 4 answer policy | More elaborate prompt and minimum/maximum word targets | Output length can dominate local inference | A meaningful generation cost, but these prompt/profile settings predate the latest indexing/isolation change range. |
| Streaming | Iterates model output and forwards each non-empty chunk through a synchronous callback to an NDJSON queue | Should improve perceived first-token latency | The backend now always uses `stream()` when available. Callback/queue overhead is possible but is not sufficient evidence for the observed model timeout. |
| Continuous indexing process | CPU extraction, GPU embedding, Qdrant writing in a separate process | No logical request dependency | Can still contend for CPU, RAM, GPU, and VRAM with Ollama. This is a key unmeasured infrastructure risk. |
| Persistence | Writes user/assistant turn and metadata after generation | Normally short and occurs after generation | Cannot cause the reported generation timeout. |

The timeout ceilings are failure boundaries, not performance targets. A 120-second generation ceiling does not itself make generation slower; it makes a slow generation fail at that boundary.

# Request Lifecycle Analysis

| Stage | Current implementation and purpose | Expected latency | Possible regression points | Available telemetry |
|---|---|---:|---|---|
| Frontend submit | `ChatPanel.handleSend()` refreshes `/api/system/status`, builds the request, then calls `streamQuestion()` | Status probe plus network setup; normally low seconds or less | Status preflight adds a request; browser uses a 150-second terminal watchdog; React updates streaming text as chunks arrive | Browser elapsed time, stage events, client timeout; no browser-side first-byte/first-token histogram |
| API route | `POST /api/chat/stream` authenticates, creates an opaque request ID, launches one worker thread, and emits NDJSON | Milliseconds before service work | Queue/thread scheduling; one event queue per request; terminal watchdog | Route elapsed time and emitted stage events |
| Validation | Engine readiness, response profile, selected context, and conversation binding | Documented target under 100 ms for permission validation | PostgreSQL access, selected-folder/document expansion, unavailable database | `request.validating` and `context.building` events; only part is summarized as permission validation |
| Access boundary | Resolves authorized relative paths and intersects selected scope | Normally below one second; documented validation target under 100 ms | Large authorized path sets, DB query latency, scope hydration | Duration and documents searched; no DB-query breakdown |
| Published generation | Uses loaded active generation; refresh discovery runs in a daemon thread | Near-zero in request path | Unexpected lock contention or a missing generation; current refresh takes a 50 ms opportunistic query lock only when swapping BM25 | Loaded generation IDs, refresh-running flag |
| Query lock | Serializes the shared pipeline for mutable per-request filters/config | Wait capped at 5 seconds | Concurrent chats wait or fail even if Ollama could serve concurrently | Failure is visible as query-capacity timeout; successful wait duration is not separately recorded |
| Query pipeline | Calls `pipeline.answer(question)`, never `pipeline.run(question)` | Dominated by retrieval and generation | Accidental re-entry into batch lifecycle was the fixed hang; current helper explicitly selects `answer()` | Stage trace and safe debug snapshot |
| Dense retrieval | Qdrant query with authorization and published-version filters | Objective below 500 ms; configured query timeout 3 seconds and hard ceiling 30 seconds | Qdrant latency, large `MatchAny` filters, retries, embedding of query | Start/completion, duration, candidate count, error/timeout state |
| BM25 retrieval | In-memory published snapshot with authorized sub-index cache | Objective within total pre-generation target; hard ceiling 10 seconds | Cache miss, large authorization scope, snapshot mismatch | Start/completion, duration, count, error/timeout |
| Fusion | Reciprocal Rank Fusion over surviving branches | Objective below 200 ms; ceiling 5 seconds | Unexpected candidate volume or worker/thread delay | Duration, count, timeout/degradation |
| Reranking | Cross-encoder scores a bounded candidate set, nominal top 30 and selected-scope expansion bounded to 250 | Objective below 2 seconds; ceiling 15 seconds | Reranker device fallback, lazy/cache behavior, CPU/GPU contention | Duration, candidate count, configured/resolved device in stage telemetry |
| Evidence selection | Applies score, diversity, redundancy, count, and token-budget rules | Expected sub-second; ceiling 5 seconds | Token counting, pathological candidate metadata | Duration, selected count, timeout; detailed counts remain in response/run trace rather than the safe live monitor |
| Context construction | Fits selected evidence under application budgets | Expected sub-second to low seconds | Larger selected chunks, citation headers, tokenizer work | Pipeline metrics and detailed trace contain token counts; live `/api/chat/debug` does not expose them |
| Prompt creation | Renders the Phase 4 system prompt plus structure/content fragments, evidence, and question | Milliseconds | Detailed prompt has substantial fixed instructions; exact size varies with evidence and profile | Prompt tokens are computed in the internal question trace after a successful answer, but not emitted in live safe stage telemetry and unavailable on timeout |
| Ollama initialization | On first evidence-bearing request, `create_local_llm()` calls `Client.list()` and creates `OllamaLLM` | Model list should be quick; actual model load may be seconds to tens of seconds | LLM is lazy; installation check is not preloading; no explicit keep-alive | Availability only; no runner/model-load metric |
| Ollama generation | `OllamaLLM.stream(prompt)` is iterated; total generation timer is checked between yielded chunks | Formerly reported 10–20 seconds; current ceiling 120 seconds | Cold load, prompt prefill, long output, slow token rate, GPU contention, partial/CPU offload, synchronous token callback | Total generation duration and success/failure; missing TTFT, prompt eval, eval count/rate, load time, placement |
| Streaming/response | Each chunk is synchronously placed on the route queue and serialized as NDJSON; frontend appends it | Should expose early progress | Per-chunk callback/event/render overhead; proxy buffering despite `X-Accel-Buffering: no`; client abort at 150 seconds | Token events carry elapsed time, but no explicit first-token aggregation |
| Citation/persistence | Builds source DTOs and saves the turn in PostgreSQL | Normally below one second to a few seconds | Large metadata/evidence snapshots, DB commit | Citation count and overall time; no persistence-duration operational metric beyond route stage |

# Evidence From Logs

## Confirmed facts

- The supplied sequence reaches successful request validation, access-boundary resolution, published-generation loading, and retrieval completion.
- The terminal example is emitted by `Phase4RAGPipeline._generate_grounded_answer()` when elapsed generation time exceeds `generation_timeout_seconds`.
- The configured default generation ceiling is 120 seconds. Backend and browser request watchdogs are both 150 seconds.
- Current production chat selects the query-only `answer()` method. The service rejects an absent answer method and does not use `run()` for live chat.
- The earlier retrieval hang was caused by `run()` interpreting intentionally absent production `documents` and `embeddings` as batch work. The current documentation and code agree that this has been corrected.
- The LLM is `gemma3:12b` by default and is created lazily. It is retained on the live pipeline after creation; it is not intentionally reconstructed for every request.
- `create_local_llm()` sets temperature and HTTP timeouts only. It does not set `keep_alive`, `num_ctx`, `num_predict`, GPU-layer placement, or other Ollama runtime options.
- The generation deadline is cumulative across Phase 4 attempts and cooldowns after `_generate_grounded_answer()` starts. Model installation checking immediately before first generation is outside that timer, while Ollama runner loading during `stream()` is inside it.
- A retry is not attempted after any output chunk has been emitted. A deadline-exhausted attempt is also not retried.
- Conversation messages are persisted, but prior message history is not appended to the current RAG question or prompt in the reviewed chat path.
- Retrieval telemetry writes to the PostgreSQL `retrieval_events` table remain deferred. Operational telemetry is in-process/log-based.
- The repository contains no captured runtime log file with the example event, so this investigation can analyze the supplied event and logger implementation but cannot reconstruct its real timestamps, prompt, hardware state, or Ollama statistics.

## Likely causes

- Ollama is doing substantially more elapsed work than before, or is receiving substantially less effective compute throughput.
- Shared GPU/VRAM pressure from the continuously running embedding process is a plausible architecture-related cause. The indexer is designed to use CUDA/FP16 automatically, and its documented validation reached 100% GPU utilization in an isolated embedding sample.
- Cold loading/eviction is plausible because the model is lazy and keep-alive is not controlled or measured.
- Low tokens-per-second or CPU/partial offload is plausible because no Ollama placement metric is recorded.
- Output length is a plausible contributor. Standard generation asks for 250–700 words, detailed for 350–2,000, and operational/elite have no explicit maximum. No hard inference token limit is passed to Ollama.

## Unknown areas requiring measurement

- Whether slow requests are cold or warm Ollama requests.
- Whether `ollama ps` shows 100% GPU, partial GPU/CPU, or CPU processing.
- Actual prompt tokens, prompt-evaluation duration, and final context tokens for failed requests.
- Actual output tokens before timeout and effective tokens per second.
- Time to first token versus time spent decoding after the first token.
- GPU utilization and VRAM occupancy during the exact request, including concurrent indexer embedding.
- Whether the model is evicted between requests or after generation-publication/indexer events.
- Whether token callback and frontend rendering materially affect server iteration speed.
- Whether actual environment overrides differ from the documented defaults. The protected backend `.env` could not be read in this investigation.

## Logging/telemetry correctness issue affecting diagnosis

The generation failure callback currently reports duration, retry count, and model but does not include the original `TimeoutError` or an `error_state`. The service normalizes a failed stage without an error type to `error_state="failed"`, not `timeout`. The original timeout is then wrapped in `GenerationFailedError`.

As a result, the raw exception log can contain the exact timeout while `/api/chat/debug`, the stream failure payload, or the administrator monitor may record `failed_stage="generation"` without `timeout_state="timed_out"` or the exact timeout reason. This does not cause the regression, but it weakens the documented promise that operational telemetry identifies the precise generation timeout.

# Generation Pipeline Investigation

## Ollama request flow

1. A request completes retrieval and context construction.
2. If the pipeline has no LLM yet, `create_local_llm()` queries the local Ollama model list with a timeout of up to five seconds.
3. It constructs `langchain_ollama.OllamaLLM(model="gemma3:12b", temperature=0, timeout=120)`.
4. Phase 4 renders a detailed grounded prompt from selected context.
5. It calls `llm.stream(prompt)` and iterates returned chunks.
6. Each non-empty chunk is accumulated and synchronously forwarded to the route callback.
7. Between chunks, the pipeline checks the total generation elapsed time and raises the configured timeout after 120 seconds.

## Model loading and keep-alive

- The application checks whether the model is installed; it does not preload the model.
- The first request with usable evidence initializes the adapter lazily.
- No explicit `keep_alive` is passed. Effective residency therefore depends on Ollama/server defaults and external model activity.
- The application health probe uses `/api/tags`, which proves installation, not that the model runner is loaded or GPU-resident.
- The administrator monitor exposes installed/loaded model labels from the health response but not Ollama load duration, processor split, or eviction history.
- There is no evidence of application-level reconstruction on every request. Publication refresh mutates the BM25 snapshot on the current pipeline rather than replacing the LLM. Repeated reload remains possible at the Ollama server layer and requires verification.

## Streaming support

Streaming is active whenever the adapter exposes `stream()`, even for callers without a token callback. This was made unconditional in the recent generation-boundary change. For browser chat, tokens are forwarded as NDJSON.

Streaming should reduce perceived latency by surfacing output early, but it does not reduce total decode work. The synchronous callback and per-chunk queue/serialization/render path add overhead. That overhead is currently unmeasured. Because the backend itself raises the 120-second generation timeout, browser rendering alone cannot explain the full failure, although synchronous callback cost can contribute to elapsed generation time.

## Timeout behavior

- Ollama HTTP timeout: 120 seconds by default.
- Phase 4 elapsed generation timeout: 120 seconds.
- Query lock acquisition timeout: 5 seconds.
- Server stream terminal watchdog: 150 seconds.
- Browser stream terminal watchdog: 150 seconds.
- Generation retries: two retries after the first attempt, with 20-second cooldowns, only for retryable pre-token failures while the cumulative deadline remains available.

The identical Ollama transport and pipeline timeouts make it difficult to distinguish a server-side inference stall from the pipeline's elapsed deadline. The timeout is a symptom boundary, not evidence that 120 seconds is too short or the cause of the slowdown.

## Prompt construction and context size

Current default bounds:

- dense top-k: 10;
- BM25 top-k: 10;
- reranker candidate top-k: 30;
- selected evidence: minimum 3, maximum 8;
- selected evidence target: 800–1,500 tokens;
- selected evidence hard budget: 2,400 tokens;
- final context ceiling: 4,096 tokens.

The Phase 4 prompt adds detailed grounding rules, enterprise-synthesis requirements, adaptive section guidance, content requirements, minimum/maximum word instructions, selected evidence, and the question. The fixed instruction portion is materially larger than the older concise `grounded_qa` prompt, and prompt prefill can therefore be meaningful on local hardware.

However, the Phase 4 prompt system and these context/evidence defaults were not changed by the recent continuous-indexing/chat-isolation/observability commit range reviewed. A larger current prompt must be demonstrated per request, not inferred solely from the architecture diagram.

## Token limits and generation profiles

| Profile | Minimum words | Maximum words | Detail |
|---|---:|---:|---|
| quick | 120 | 250 | concise |
| standard | 250 | 700 | detailed |
| detailed | 350 | 2,000 | detailed |
| operational | 350 | none | detailed |
| elite | 350 | none | detailed |

These limits are natural-language prompt instructions. They are not enforced through `num_predict`, and generated output is not truncated to the requested maximum by application code. Long output at a low decode rate can therefore approach the 120-second ceiling. The frontend defaults and request-specific profile for the example were not supplied.

## CPU fallback and GPU risks

- The query service records its embedding model device and reranker readiness, while the indexer records embedding GPU utilization and memory.
- None of these establish where Ollama placed `gemma3:12b`.
- The standalone indexer defaults to automatic device selection and FP16 on CUDA, with adaptive embedding batches up to 256 and a 70% VRAM target.
- The architecture isolates index validity and request dependencies, but not the physical accelerator. Ollama and BGE-M3 may therefore compete for VRAM bandwidth, compute, power/thermal headroom, or force partial model offload.
- A model that previously fit fully in VRAM may become partially CPU-offloaded while the indexer model/batch is resident. This would be consistent with a sharp generation slowdown, but it is not confirmed by current telemetry.

# Retrieval vs Generation Isolation

The present evidence favors generation latency over retrieval latency:

- retrieval starts and completes before `generation_started`;
- the supplied terminal exception originates inside the model-output loop;
- the fixed `run()`/`answer()` boundary prevents corpus loading and embedding in chat;
- hybrid branches, fusion, reranking, and evidence selection have hard ceilings and degradation behavior;
- the documented normal pre-generation objective is below three seconds.

That does not prove retrieval performance is unchanged. It only shows retrieval is not the terminal stage in the example. The correct comparison for matched old/new questions is:

| Workload measure | Current code can compute it? | Present in live operational telemetry? | Needed comparison |
|---|---:|---:|---|
| Dense result count | Yes | Candidate count/duration | Old vs new |
| BM25 result count | Yes | Candidate count/duration | Old vs new |
| Fused candidate count | Yes | Candidate count/duration | Old vs new |
| Reranked candidate count | Yes | Candidate count/duration | Old vs new |
| Selected chunk count | Yes | Selected count is partially available | Old vs new |
| Candidate tokens | Yes | Detailed trace only | Old vs new |
| Selected evidence tokens | Yes | Detailed trace only | Old vs new |
| Final context tokens | Yes | Detailed trace only | Old vs new |
| Final prompt tokens | Yes after response construction | Detailed successful trace only; absent on failed live request | Old vs new |
| Output tokens | Estimated by application tokenizer after success | Not in live operational metrics | Old vs new |

The most important isolation experiment is a matched question under four observed states: warm Ollama/indexer idle, warm Ollama/indexer embedding, cold Ollama/indexer idle, and cold Ollama/indexer embedding. Without that matrix, prompt workload, model loading, and physical contention remain confounded.

# Telemetry Gap Analysis

| Required metric | Current availability | Gap |
|---|---|---|
| Prompt token count | Computed in successful internal Phase 3/4 question traces | Not emitted in live stage telemetry; unavailable when generation fails before response trace completion |
| Context token count | Computed as `final_context_tokens` and in trace | Not exposed by `/api/chat/debug` or admin query snapshot |
| Output token count | Computed after successful answer using the application tokenizer | No live value; no count for partial timed-out output |
| First-token latency | Token events have elapsed request time | No explicit generation-start-to-first-token metric or aggregation |
| Tokens per second | Not calculated | Missing |
| Model load time | Ollama response statistics are discarded/not requested | Missing |
| Ollama generation duration | Coarse pipeline generation duration exists | Missing Ollama-native `total_duration`, `load_duration`, `prompt_eval_duration`, and `eval_duration` |
| GPU utilization during generation | Indexer heartbeat provides sampled GPU values | Not request-correlated; not Ollama-specific |
| VRAM usage during generation | Indexer heartbeat provides sampled device memory | Not request-correlated; cannot attribute memory to Ollama vs embedding |
| Ollama processor placement | Not recorded | Missing `%GPU`/CPU offload state from `ollama ps` |
| Retrieval duration by stage | Dense, BM25, fusion, reranker, generation and total are present in debug/monitor; evidence/context coverage is partial | Evidence selection and context construction are not fully projected in the admin query summary |
| Query-lock wait | Failure at 5 seconds is visible | Successful wait time is missing |
| Retry/cooldown timeline | Retry count and logs exist | No structured per-attempt start/end, TTFT, load, or remaining-deadline metrics |
| Exact timeout reason | Raw exception log contains it | Generation callback omits timeout error state, so safe operational projections can lose the timeout classification |
| Durable query history | `retrieval_events` schema exists | Production writes are intentionally deferred, preventing longitudinal old/new request comparison |

The existing telemetry is sufficient to identify the broad failed stage, but not to distinguish cold load, prompt prefill, slow decode, CPU offload, GPU contention, or streaming callback overhead.

# Root Cause Ranking

| Possible Cause | Evidence | Confidence | Needs Verification |
|---|---|---|---|
| Shared GPU/VRAM contention with continuous indexing | Indexer is a concurrent process, defaults to auto/CUDA FP16, can reach high GPU utilization, and no resource coordination with Ollama is present. Failure is in generation. | Medium–High | Correlate request IDs with indexer embedding state, `nvidia-smi`, per-process VRAM, and Ollama placement. |
| Ollama model reload/cold load | LLM is lazy; health checks prove installation only; no explicit `keep_alive`; load duration is not measured. | Medium | Compare first vs immediate repeated request; inspect `ollama ps` before/during/after; capture Ollama load duration. |
| GPU fallback or partial offload | No telemetry identifies Ollama processor split. Concurrent BGE-M3 residency can reduce available VRAM. | Medium | Record `ollama ps` processor percentage and process-level GPU memory during the request. |
| Increased output workload / low decode rate | Standard asks for 250–700 words; detailed can request 2,000; some profiles have no maximum; no `num_predict`. | Medium | Capture selected profile, partial/final output tokens, TTFT, decode duration, and tokens/sec for matched questions. |
| Increased prompt size | Detailed prompt and up to 2,400 evidence tokens can make prefill non-trivial. Exact failed-request prompt size is absent. Recent reviewed changes did not alter generation prompt or token budgets. | Medium–Low | Compare old/new final prompt and context tokens for the same question and generation/profile. |
| Increased context size from retrieval/reranking output | New publication can select different chunks even with unchanged bounds. Selected evidence is capped and targeted. | Medium–Low | Compare retrieved/fused/reranked/selected counts and token totals on matched generations. |
| Generation timeout configuration | The 120-second ceiling directly produces the observed exception but does not cause inference to slow down. It may expose a workload that now exceeds the bound. | Low as root cause; High as failure trigger | Measure uncensored Ollama timings in an isolated diagnostic run without changing production behavior. |
| Streaming regression | Recent code always uses `stream()` and synchronously calls the token callback. This may add per-chunk overhead. Streaming ordinarily improves perceived TTFT, and the backend timeout still points to server elapsed generation. | Low–Medium | Compare Ollama-native generation duration to pipeline duration and count callback chunks without changing production. |
| Conversation history expansion | History is persisted, but prior turns are not included in the reviewed RAG prompt. Session ID is used for ownership/telemetry. | Very Low | Confirm a trace from a long session and a new session has identical prompt size for the same scoped question. |
| Retrieval regression | Known hang was fixed; logs say retrieval completes; failure is generation. Retrieval can still add some latency but does not explain the shown timeout. | Low | Retain actual dense/BM25/fusion/reranker/selection durations for matched requests. |
| Prompt-management lookup/cache overhead | Prompt files are validated/cached and rendered locally; no network call is involved. | Very Low | A local render timing would close the question, but it cannot plausibly account for 90–120 seconds. |
| Frontend/proxy buffering | Could delay visible tokens, but cannot by itself cause the backend's Phase 4 elapsed-generation timeout. | Very Low for backend timeout | Compare server token timestamps with browser receipt timestamps. |

# Recommended Diagnostic Steps

These are investigation steps only; they do not prescribe code, configuration, migration, or architecture changes.

1. **Capture one complete matched request trace.** Use the same question, profile, selected scope, active generation, and model. Retain timestamps for validation, access resolution, dense, BM25, fusion, reranking, selection, context construction, generation start, first token, final token/error, and total time.
2. **Repeat the matched question immediately.** Compare a likely cold first request with a warm second request. A large first-only delta would support model load/eviction.
3. **Observe `ollama ps` at generation start and during generation.** Record model name, processor split, context allocation, and residency. Do not infer GPU placement from indexer telemetry.
4. **Monitor `nvidia-smi` during the exact request.** Record timestamped GPU utilization, total/free VRAM, and per-process VRAM for Ollama and the indexer. Correlate samples with the request ID and stage timestamps.
5. **Run the matched state matrix:** indexer idle vs actively embedding, crossed with Ollama cold vs warm. Compare TTFT and tokens/sec. This directly tests the strongest architecture-related contention hypothesis.
6. **Collect Ollama-native timing fields.** For the diagnostic request, retain total duration, load duration, prompt evaluation count/duration, output evaluation count/duration, and done reason. These distinguish loading, prefill, and decode.
7. **Compare old/new workload sizes.** For the same question, compare retrieved chunk count, fused candidates, reranked candidates, selected chunks, candidate tokens, selected evidence tokens, final context tokens, prompt tokens, and requested profile.
8. **Count partial output on timeout.** Determine whether the timeout occurs before the first token, after a small number of very slow tokens, or near completion of a long response.
9. **Correlate model eviction with other Ollama consumers.** Check whether summary generation, message transformation, or other local-model activity runs between chat requests and changes model residency.
10. **Compare pipeline elapsed generation with Ollama-native duration.** A large excess in pipeline time would implicate callbacks, queueing, retries/cooldowns, or client transport; similar values would implicate Ollama inference/runtime.
11. **Review actual environment values through an authorized operational channel.** Confirm model name, generation/request timeouts, retry count/cooldown, indexer device, reranker device, and profile defaults without changing them.
12. **Inspect request concurrency.** Record query-lock acquisition/wait and active chat count. This will separate serialized queue delay from model generation time.
13. **Compare server and browser token timestamps.** This tests proxy buffering and per-token frontend update overhead separately from backend inference.
14. **Retain several consecutive traces, not one sample.** At minimum capture cold, warm, indexer-idle, and indexer-active cases. Report median and tail latency rather than relying only on the timeout sample.
15. **Reconcile raw logs with `/api/chat/debug` and the admin monitor.** Verify whether generation timeouts are classified as timed out or merely failed; treat the raw chained `TimeoutError` as authoritative where projections lose the reason.

# Files Reviewed

## Required source-of-truth documents

- `services/knowledge-engine/docs/backend/CURRENT_STATE.md`
- `docs/architecture/CONTINUOUS_INDEXING_ARCHITECTURE.md`
- `docs/architecture/SEARCH_AND_RETRIEVAL_OBSERVABILITY.md`
- `docs/architecture/FULL_STACK_INTEGRATION.md`
- `docs/architecture/FRONTEND_MIGRATION_MANIFEST.md`
- `docs/architecture/DATABASE_ARCHITECTURE.md`
- `docs/architecture/PROMPT_ARCHITECTURE.md`
- `services/knowledge-engine/docs/backend/AUTOMATED_EVALUATION.md`

## Additional architecture/observability reference

- `frontend/docs/FRONTEND_MIGRATION_MANIFEST.md`
- `services/knowledge-engine/docs/backend/execution_observability.md`

## Backend request and runtime path

- `services/knowledge-engine/backend/app/api/routes/chat.py`
- `services/knowledge-engine/backend/app/services/knowledge_engine_service.py`
- `services/knowledge-engine/backend/app/services/startup_service.py`
- `services/knowledge-engine/backend/app/services/admin_system_monitor_service.py`
- `services/knowledge-engine/backend/app/services/system_status_service.py`
- `services/knowledge-engine/backend/app/services/conversation_service.py`
- `services/knowledge-engine/backend/app/repositories/chats.py`
- `services/knowledge-engine/backend/app/schemas/chat.py`
- `services/knowledge-engine/backend/app/core/config.py`
- `services/knowledge-engine/backend/app/core/application_config.py`

## Retrieval, context, prompt, generation, and telemetry implementation

- `services/knowledge-engine/src/cial_knowledge_os/config.py`
- `services/knowledge-engine/src/cial_knowledge_os/rag_pipeline.py`
- `services/knowledge-engine/src/cial_knowledge_os/phase2_pipeline.py`
- `services/knowledge-engine/src/cial_knowledge_os/phase3_pipeline.py`
- `services/knowledge-engine/src/cial_knowledge_os/phase4_pipeline.py`
- `services/knowledge-engine/src/cial_knowledge_os/llm.py`
- `services/knowledge-engine/src/cial_knowledge_os/retrieval.py`
- `services/knowledge-engine/src/cial_knowledge_os/retrievers.py`
- `services/knowledge-engine/src/cial_knowledge_os/retrieval_trace.py`
- `services/knowledge-engine/src/cial_knowledge_os/retrieval_postprocessing.py`
- `services/knowledge-engine/src/cial_knowledge_os/reranker.py`
- `services/knowledge-engine/src/cial_knowledge_os/context_builder.py`
- `services/knowledge-engine/src/cial_knowledge_os/execution/telemetry.py`
- `services/knowledge-engine/src/cial_knowledge_os/execution/events.py`
- `services/knowledge-engine/src/cial_knowledge_os/execution/metrics.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/registry.yaml`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/manager.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/loader.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/renderer.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/cache.py`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/phase4_system.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/adaptive_sections.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/adaptive_content_requirements.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/minimum_words.md`
- `services/knowledge-engine/src/cial_knowledge_os/prompts/generation/phase4/maximum_words.md`

## Frontend streaming path

- `frontend/src/api/client.ts`
- `frontend/src/api/types.ts`
- `frontend/src/components/assistant/ChatPanel.tsx`
- `frontend/tests/chat-timeout-progress-regression.test.mjs`

## Change history inspected

The repository history and diffs were inspected for the generation, chat, service, and configuration paths, including the changes that introduced response profiles, streaming, continuous indexing, generation/retrieval deadlines, chat isolation, query-only execution, and retrieval telemetry. In particular, the current tree was compared with the pre-continuous-indexing chat instrumentation revision `595b617`.

# Final Conclusion

The most likely immediate bottleneck is **local Ollama generation**, with **GPU/VRAM availability, model residency, and effective inference throughput** as the leading underlying areas to test. The evidence for that conclusion is strong at the subsystem level:

- validation and access checks succeed;
- a valid published generation is loaded;
- retrieval completes;
- the stack enters Phase 4 generation;
- the exception is raised by the elapsed-time check inside the Ollama stream loop.

The known retrieval hang is not the same failure and is already removed by the query-only `answer()` boundary. Retrieval could still have changed modestly, or could deliver a larger context, but it does not account for the shown terminal stage.

No single physical cause is proven. The current telemetry cannot distinguish:

- cold model load from warm inference;
- long prompt prefill from slow output decoding;
- fully GPU-resident execution from partial or CPU fallback;
- Ollama work from synchronous streaming overhead;
- normal inference from contention with the continuous indexer's GPU embedding.

The strongest architecture-linked hypothesis is that continuous indexing is **logically isolated but not physically isolated** from generation. Concurrent BGE-M3 GPU work can affect Ollama even though chat never waits on indexing jobs or rebuilds an index. The strongest generation-policy hypothesis is that a detailed, potentially long response is being decoded without a hard Ollama output-token limit at a lower-than-before token rate. Cold model loading is also credible because the adapter is lazy and keep-alive/load duration are unobserved.

The decisive next evidence is a request-correlated generation trace containing prompt/context/output tokens, TTFT, tokens/sec, Ollama-native load/prompt-eval/eval durations, `ollama ps` placement, and GPU/VRAM samples while the indexer is both idle and active. Until those measurements exist, the correct conclusion is **generation/infrastructure regression with high localization confidence, but only medium confidence in the ranked underlying causes**.
