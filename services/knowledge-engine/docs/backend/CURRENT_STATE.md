# CIAL Knowledge OS: Current State through Phase 5

Last audited: 2026-07-29

This document describes the implemented repository state. `PROJECT_REQUIREMENTS.md`
defines the binding requirements, while this file distinguishes completed
capabilities from planned work.

## Adaptive Appearance Control

The production frontend now exposes one shared Light/System/Dark segmented
control in the expanded desktop sidebar, collapsed 64px rail, and mobile
drawer. It retains the existing `next-themes` provider, `cial-theme` storage
contract, startup bootstrap, live system-theme resolution, and all dark-mode
tokens. Expanded and mobile layouts are horizontal; the collapsed rail uses a
40x114px vertical icons-only form with tooltips. Mobile labels respond to the
control container and hide at 270px or narrower.

The control is a labelled radio group with roving focus, orientation-aware
arrow keys, Home/End navigation, visible focus, reduced-motion handling, and
focus restoration when the desktop control changes orientation. The focused
Playwright verifier passed 20 checks on 2026-07-29 across desktop, collapsed,
mobile, explicit and System preferences, live OS-theme changes, persistence,
route/reload continuity, keyboard behavior, responsive overflow, and reduced
motion. Its machine-readable evidence and screenshots are under
`outputs/playwright/appearance-toggle/`.

## Authenticated Conversation Persistence

The current FastAPI integration persists authenticated conversation history in
PostgreSQL `chat_sessions` and `chat_messages` through `ChatRepository`.
Successful turns retain the stable session id, user and assistant messages,
citations, sources, selected context ids, response profile/metadata, and
timestamps. List and read queries are constrained by the authenticated user;
another user's session id returns not found. Browser storage is not a history
store, and an empty database or API failure does not activate demo data.

## Admin AI Operations Console

The production frontend now has an administrator-only operations route at
`/admin/system-monitor`. The route is absent from normal-user navigation and
renders a local 403 access-denied surface unless the authenticated profile has
`monitor_system` or `manage_settings`. Backend authorization remains
authoritative: both `GET /api/admin/system/monitor` and
`GET /api/admin/system/stream` resolve the current PostgreSQL RBAC graph and
return 403 to an authenticated principal without either grant.

The console is a projection of real runtime sources, not a separate analytics
store. It combines the bounded dependency probes from `SystemStatusService`,
durable `indexing_jobs`, `indexer_workers`, and `index_generations` state,
standalone-indexer CPU/GPU/throughput samples, live query-runtime model
diagnostics, and the query pipeline's safe stage timings. It exposes
infrastructure cards, the active indexing pipeline, GPU/CPU workers, model
readiness, query latency, priority queues, failures, and a bounded operational
event stream without prompts, document content, credentials, or raw exception
messages.

The stream uses authenticated server-sent events. The browser performs an
authorized snapshot preflight, then consumes the SSE feed with credentials,
bounded exponential reconnect, explicit connection state, and stale-data
detection. Last-known values remain visible during a partial failure and are
labelled stale rather than replaced with invented healthy values. Query start
and completion/failure events come from the actual chat route lifecycle;
indexing events are derived from durable job-state, worker-state, and published
generation transitions.

## Project Overview

CIAL Knowledge OS is an enterprise-grade, fully offline, notebook-first
retrieval-augmented generation (RAG) platform for enterprise documentation. The
current repository is an experimentation and reusable-module foundation, not yet
a production service or user interface.

The platform is designed around these principles:

- offline-first operation on organization-controlled infrastructure;
- open-source and open-weight local models;
- no cloud inference or cloud vector database;
- notebook-first, inspectable experimentation;
- reusable production-oriented modules under `src/cial_knowledge_os/`;
- configuration-driven and reproducible behavior;
- model-agnostic interfaces;
- token-efficient evidence selection and prompting; and
- enterprise-ready traceability, safe failure, and extension boundaries.

## Current Architecture

```text
Enterprise documents in configured data/files/ taxonomy
  -> Enterprise File Format Registry validation and readiness scan
  -> recursive supported-document loading plus OCR-supported image extraction
  -> metadata-preserving chunking
  -> local embeddings
  -> embedded local Qdrant (default) or local Docker Qdrant server (opt-in)
  -> selectable dense, BM25, or hybrid retrieval
  -> Reciprocal Rank Fusion in hybrid mode
  -> Phase 2 query variants and multi-query evidence collection
  -> Phase 4 local cross-encoder reranking
  -> explainable evidence selection
  -> overlap merging and token-aware or character-compatible context construction
  -> grounded local Ollama generation
  -> clickable citations, evidence quality, traces, run bundles, and offline evaluation
```

Notebooks are the learning and orchestration layer. Reusable behavior belongs in
`src/cial_knowledge_os/`, where ingestion, chunking, embeddings, vector storage,
retrieval, generation, context construction, evaluation, exports, and
visualization are split into focused modules. Configuration is centralized in
`KnowledgeOSConfig`, `Phase2Config`, `Phase3Config`, and `Phase4Config`;
experiment sweeps add declarative `ExperimentConfig` and `ExperimentGrid`
values.

`KnowledgeOSConfig.knowledge_root` resolves to `data/files/`, the canonical
enterprise source repository. Files may be nested to any depth; the first folder
is recorded as `category` and the second, when present, as `collection`.
Recommended top-level categories include `aviation`, `cybersecurity`,
`engineering`, `hr`, and `legal`, with standards bodies, systems, or document
sets as second-level collections. Discovery is governed by the Enterprise File
Format Registry, which classifies files as `SUPPORTED_NOW`, `OCR_SUPPORTED`,
`RECOGNIZED_FUTURE_SUPPORT`, or `UNSUPPORTED`. Only `SUPPORTED_NOW` and
`OCR_SUPPORTED` files enter extraction, chunking, embedding, and indexing.
Recognized future and unsupported files are logged, skipped, and reported.

Currently processed formats include PDF, DOCX, DOC, XLSX, XLS, CSV, PPTX, PPT,
TXT, Markdown, HTML, JSON, XML, and YAML. PNG, JPG/JPEG, and TIFF are processed
through the modular OCR subsystem before chunking. Recognized future categories
include email, archives, source code, configuration and DevOps files,
audio/video, and CAD/engineering formats.

Runtime ingestion does not search the former `data/pdf/` corpus. Missing or
empty canonical repositories produce an empty corpus rather than a fallback.
`scripts/migrate_pdf_to_files.py` remains a one-time transition utility: it
copies legacy PDFs to `data/files/legacy_pdf/` by default and supports
`--dry-run` and explicit `--move` modes.

Production indexing is continuous and runs in the standalone
`backend/indexer_main.py` process. Filesystem events and periodic reconciliation
enqueue durable PostgreSQL jobs; FastAPI startup never scans, chunks, embeds, or
rebuilds the corpus. The indexer fingerprints stable files, skips unchanged
content, batches chunks across documents, verifies each new Qdrant document
version before deleting stale points, and atomically publishes generation-tagged
BM25 snapshots. The legacy manifest-driven `index()` path, including
`incremental_indexing_enabled` and `force_rebuild_index`, remains available only
to frozen notebooks and explicit batch experiments.

Production chat is isolated from continuous indexing. A request uses the
already-loaded, verified `index_generations.name='active'` publication and
triggers pointer discovery asynchronously. It never polls indexing jobs, waits
for queue drain, reads worker heartbeat state, or joins extraction/embedding
work. A pending or failed update leaves the previous generation serving; a
first deployment without a valid published generation returns controlled
unavailability. Dense retrieval is pinned to document versions and note
revisions present in the loaded publication, so in-place Qdrant writes cannot
expose a partially prepared generation.

The live service invokes the loaded pipeline's query-only `answer()` path.
It must never invoke the batch `run()` lifecycle: that lifecycle interprets
the intentionally absent production `documents` and `embeddings` fields as
work to perform and would load source files and embed the published BM25
snapshot before retrieval. Query-time BM25 rebuilding is also rejected in the
production authorization-aware runtime.

The production BM25 runtime loads only the active generation's atomic snapshot.
At startup or asynchronous publication refresh it materializes the chunk set,
loads/reuses cached tokens, constructs one `BM25Okapi`, and builds immutable
term-posting and relative-path index maps. A query does not read snapshot JSON,
source documents, the full tokenized corpus, or construct a scope-specific
BM25 model. It scores query-term postings from that loaded publication, filters
them with the authorized path-index set, and selects the bounded top candidates.

Phase 1 retrieval infrastructure is initialized before API readiness. The
dense query embedding model performs one discarded readiness embedding; the
cross-encoder loads cache-first, resolves `auto` to CUDA when available or CPU
otherwise, and performs one discarded readiness batch. BM25 remains the single
in-memory active publication. These readiness probes do not write Qdrant or
enter retrieval results.

Hybrid dense and BM25 branches execute concurrently for the same query,
candidate limits, authorization filters, and publication. Their rankings feed
the unchanged RRF logic. Cross-encoder reranking already uses one batched
`predict()` over the complete ordered candidate pool; no per-candidate model
loop is used.

The 2026-07-26 regression investigation used the real generation-29 snapshot:
1,049,687,710 bytes, 459,715 chunks, and 488 document identifiers. The prior
cold broad-scope query-time model build measured 15,626 ms; after isolating that
fault, full-corpus score/sort still measured 828-911 ms. Published posting
searches now measured 2.48-11.15 ms across unrestricted, broad-scope, and
single-path cases. Snapshot load measured 17,194 ms and activation 35,725 ms,
both outside the request path. The BM25 search objective is below 100 ms.

Phase 1 performance validation retained 10 dense candidates, 10 BM25
candidates, 28 reranker candidates, and 8 selected evidence items. On the
RTX 5070 Ti, the reranker loaded on `cuda:0` as `torch.float32`, attributed a
90,863,104-byte load delta, and processed the 28-candidate batch without
changing scores or ordering rules. Warm repeated end-to-end retrieval measured
1,919 ms; parallel dense/BM25 was 81 ms, BM25 search 30.5 ms, fusion 2 ms,
reranking 38 ms, and evidence selection 7 ms. The first post-start probe was
2,103 ms, so the below-2-second objective is a warmed-runtime target rather
than a universal hardware guarantee.

Hard stage ceilings are Qdrant/dense retrieval 30 seconds, BM25 10 seconds,
fusion 5 seconds, reranking 15 seconds, and evidence selection 5 seconds.
Configured lower Qdrant limits and transient-only retries still apply inside
the 30-second dense ceiling. Retrieval timeouts return authorization-filtered
results from the surviving branch where possible; reranker timeout preserves
the bounded fused order; evidence-selection timeout returns no evidence rather
than generating from unselected material. Local Ollama streaming remains
bounded by the 120-second generation timeout. Chat lock acquisition is limited
to 5 seconds, and streaming has a 150-second terminal watchdog. Structured
stage telemetry and authenticated `GET /api/chat/debug` expose safe timings and
the exact failed stage without query, prompt, or document content.
BM25 debug/administrator telemetry includes actual snapshot activation time and
bytes, load and in-memory activation durations, document/chunk counts, search
duration, and returned candidate count. Unavailable measurements remain null.

The current LLM adapter uses Ollama. The surrounding pipeline accepts replaceable
local model objects, but adapters for other local runtimes such as vLLM and
llama.cpp are still future work.

### Qdrant deployment modes

`KnowledgeOSConfig` provides `qdrant_mode`, `qdrant_url`,
`qdrant_api_key`, `qdrant_collection_name`, `qdrant_dir`,
`qdrant_batch_size`, and `qdrant_upsert_wait`. Omitting `qdrant_mode`
preserves the `embedded` default for batch/notebook compatibility.
`qdrant_mode="server"` uses the configured URL and performs a health probe
before indexing or retrieval. An unreachable service reports local Docker
start commands rather than a low-level connection error.

The production API and standalone indexer require server mode so both processes
can safely share the collection. Their typed environment setting defaults to
`CIAL_QDRANT_MODE=server`; embedded mode is rejected by the indexer.

Indexing constructs and submits bounded point batches rather than serializing
the full corpus update in one JSON request. The resolved default is 256 points
per embedded upsert and 32 points per server upsert. Server deployments should
retain a small batch unless measured vector and payload sizes justify a larger
value. `qdrant_upsert_wait=True` preserves synchronous completion semantics and
can be disabled explicitly when the caller accepts asynchronous server
processing. Every completed batch emits structured progress without changing
point IDs, vectors, or payload metadata.

Embedded mode remains appropriate for notebooks, demonstrations, and small
collections. The local Docker server is recommended for large collections and
concurrent clients:

```bash
docker compose -f docker-compose.qdrant.yml up -d
curl http://localhost:6333/healthz
```

Set `qdrant_mode="server"` and
`qdrant_url="http://localhost:6333"` in the active phase configuration. Stop
and start it with Docker Compose. Storage remains on-premises in the Docker
named volume `cial_qdrant_storage`; there is no Qdrant Cloud dependency. The
named volume replaces the previous Windows bind mount that could fail Qdrant
segment renames during optimization.

Read-only health inspection reports reachability, collection presence, point
and indexed-vector counts, collection and optimizer status, and embedding
dimension compatibility. Infrastructure preflight also reports offline model
flags, RAM, disk, configured GPU availability, and local Ollama availability.
A red optimizer is a warning rather than an automatic crash; an unreachable
opt-in server is a preflight error.

Existing embedded collections can be inspected or migrated without changing
the frozen notebooks:

```bash
python scripts/migrate_embedded_qdrant_to_server.py \
  --source data/qdrant/cial_phase4 \
  --url http://localhost:6333 \
  --collection cial_phase4 \
  --batch-size 512
```

The utility preserves point IDs, dense/named/sparse vector configuration,
vectors, and payloads, supports `--dry-run`, and requires `--force` before
overwriting a target collection.

## Completed Phase 1: Basic RAG

The frozen Phase 1 baseline is represented by
`notebooks/01_Basic_RAG.ipynb` and `BasicRAGPipeline`. It implements:

- recursive, configuration-driven local PDF loading with Docling and a PyMuPDF
  fallback;
- local text loading and metadata-preserving chunking;
- local SentenceTransformers embeddings;
- persistent embedded Qdrant storage;
- manifest-driven incremental Qdrant updates and safe full rebuilds;
- dense semantic retrieval;
- local Ollama generation;
- bounded grounded prompts and safe prompt instructions;
- source, page, chunk, score, and metadata-aware citations;
- basic latency benchmarking and visualizations;
- versioned batch answer CSV exports; and
- a modular package under `src/cial_knowledge_os/`.

Phase 1 is a dense top-k baseline. It does not implement the production features
listed under **Current Limitations**.

## Completed Phase 2: Query Transformations and Context Construction

The frozen Phase 2 baseline is represented by
`notebooks/02_Query_Transformations_and_Context_Construction.ipynb`,
`notebooks/testing/Phase2_Automated_Evaluation.ipynb`, and
`Phase2RAGPipeline`. It implements:

- inspectable original, rewritten, keyword-expanded, and domain-reformulated
  query variants;
- configurable multi-query dense retrieval;
- evidence fusion by collecting results from all enabled variants;
- exact deduplication by `(source, page, chunk_id)`, retaining the strongest
  score and query provenance;
- source-relative neighbor expansion;
- overlap-aware merging of contiguous chunks;
- character-bounded context construction and compression;
- one stronger grounded generation pass over the constructed context;
- explicit insufficient-evidence handling with no citations on safe failure;
- citation mapping to the final compressed evidence;
- retrieval, source, score, context, citation, answer-status, and latency
  visualizations;
- versioned batch exports with Phase 2 trace columns;
- a deterministic automated evaluation framework;
- a frozen 200-question CISG benchmark; and
- unit and regression tests for pipeline, export, visualization, and evaluation
  behavior.

The current query rewrite is deterministic string normalization. It does not call
an LLM. `QueryTransformer` supports registered local strategies, so an AI-based
rewrite can be introduced later without changing its external role. Likewise,
Phase 2 still enforces its frozen character budget. Its backward-compatible
export field now receives an exact centralized tiktoken count rather than the
former tokenizer-independent estimate.

## Implemented Phase 3: Hybrid Retrieval

`notebooks/03_Hybrid_Retrieval.ipynb` and `Phase3RAGPipeline` now implement:

- a common retriever protocol with dense and `rank-bm25` implementations;
- dense-only, BM25-only, and hybrid modes;
- proper configurable Reciprocal Rank Fusion with modality ranks and scores;
- shared chunk reuse plus fingerprinted BM25 token caching;
- centralized tiktoken-aware context fitting, truncation, and reporting;
- a packaged hash-verified `cl100k_base` vocabulary for offline tokenization;
- the unchanged Phase 2 character budget when token budgeting is disabled;
- metadata-derived `file://` and configurable localhost PDF page links;
- configurable structured logging;
- a `RunManager` with collision-safe timestamped directories;
- backward-compatible CSV plus formatted XLSX and standalone HTML reports;
- configuration, summary, retrieval, metrics, logs, figures, and per-question
  context artifacts; and
- per-question execution traces from query variants through dense/BM25
  candidates, RRF, post-processing, token budgeting, generation, citations, and
  artifact export, with notebook and standalone HTML diagnostics; and
- additive integration with the existing batch and evaluation contracts.

The implementation and offline tests are complete. Phase 3 is not yet a frozen
baseline because the full 200-question local-model comparison has not been run
in this checkout. The empirical exit gate remains a documented Phase 2 versus
Phase 3 improvement or trade-off on the unchanged frozen benchmark.

## Implemented Phase 4: Reranking and Evidence Selection

`notebooks/04_Reranking_and_Evidence_Selection.ipynb` and
`Phase4RAGPipeline` now implement:

- a lazy SentenceTransformers cross-encoder with configurable model, CPU/GPU
  device, batch size, and cache/download policy;
- cache-first loading on every process, automatic one-time staging on a
  developer cache miss, and strict no-network enterprise mode through
  `reranker_local_files_only=True`;
- a deterministic `MockReranker` with the same interface for unit and
  end-to-end tests;
- reranking after RRF, without directly averaging dense, BM25, RRF, and
  cross-encoder scores from incompatible scales;
- evidence selection using maximum count, reranker threshold, source-diversity
  cap, lexical redundancy reduction, and evidence-token budget strategies;
- a default three-chunk evidence floor, eight-chunk ceiling, adaptive ranked
  fallback, and an 800--1500 selected-token target for normal QA;
- explicit weak/mixed/strong evidence confidence plus an evidence-sufficiency
  gate that blocks extractive fallback for weak, all-fallback, or
  below-minimum-score evidence;
- deterministic current/live/external-data detection, with an
  `unsupported_query` result when indexed evidence does not directly support
  the request;
- a Phase 4-specific detailed answer style that retains Phase 3 grounding and
  citations while selecting question-relevant section families for findings,
  implications, controls, procedures, comparisons, risks/gaps, caveats, and
  next actions from selected evidence only;
- configurable `answer_detail_level`, `min_answer_words`, optional
  `max_answer_words`, `prefer_structured_answers`,
  `adaptive_answer_sections`, and `include_decision_notes` generation policy;
- Phase 4-only generation retries and cooldown for retryable local Ollama
  runner, stream, transport, HTTP 500, and memory-allocation failures;
- per-question CSV/JSONL checkpoints and indexed question-hash resume support,
  including duplicate-text safety and final failure-row preservation;
- an intentional smaller evidence budget before the existing final context
  budget;
- per-chunk evidence strength, retrieval provenance, citation availability,
  metadata completeness, and source-diversity diagnostics;
- candidate, selected, and final-context tokens; token-reduction percentage;
  discard counts and reasons; and stage latency;
- full and compact serializable traces showing retrieved, fused, reranked,
  selected, context, answer, citations, and artifact paths;
- `smoke`, `manual_qa`, `benchmark`, and `export_only` runner modes with a
  notebook-safe manual-question limit;
- additive Phase 4 CSV fields, manager-friendly XLSX, standalone offline HTML,
  JSON, log, context, and SVG decision artifacts;
- safe inline HTML citation badges for numeric and source/page/chunk answer
  markers, with compact fallback chips and collapsible citation details while
  preserving CSV/XLSX citation columns; and
- dependency-injected pipeline/reporting interfaces suitable for future
  automated benchmark execution without notebook execution.

Phase 4 reuses the Phase 3 retrievers, RRF, token manager, context builder,
citation engine, `RunManager`, batch collector, and evaluation interfaces.
Earlier classes and configuration defaults are unchanged. Phase 4 disables
neighbor expansion by default so evidence that did not pass reranking is not
introduced after selection; callers can opt in explicitly.

Long terminal runs persist `partial_results.csv`, `partial_results.jsonl`,
`partial_retrieval.jsonl`, and `checkpoint.json` after every attempt. Resume
uses the same run directory and question order, skips successful occurrences,
and retries failed or interrupted occurrences. Standard final artifacts are
regenerated even when some generation attempts remain failed.

Phase 4 distinguishes four answer outcomes. `answered` means generation
succeeded or a generator refusal was replaced by a sufficient-evidence
extractive fallback. `insufficient_evidence` means the indexed evidence cannot
support an answer or safe fallback. `unsupported_query` means the question
appears to require current/live/external data absent from the indexed evidence.
`generation_failed` means the local generator exhausted retries before a
response artifact could be completed.

Phase 4 evidence reduction is not an answer-length optimization. Detailed
synthesis is generated from the smaller, higher-precision selected context.
Word targets apply only when evidence supports them and do not permit padding
or unsupported claims.

Phase 4 now supports semi-adaptive answer sections. The default prompt chooses
only section families that fit the question shape; setting
`adaptive_answer_sections=False` restores the previous fixed template for
reproducibility. This Phase 4 mechanism is not the full response planner; the
optional Phase 5 layer now provides that planner. Neither change establishes a
benchmark-qualified quality improvement.

The default `reranker_local_files_only=False` is a developer-experience policy,
not a cloud-inference dependency. Loading remains lazy and always tries the
local Hugging Face cache first. Only a cache miss permits a model download,
which is cached for subsequent offline runs. Enterprise deployments set the
field to `True`; a missing model then produces an actionable error without any
network attempt. Automated tests continue to inject `MockReranker`.

The implementation and deterministic automated tests are complete. Phase 4 is
**implemented but not benchmark-qualified** because the full unchanged
200-question Phase 3 Hybrid versus Phase 4 Reranked Hybrid comparison has not
been run with the approved local corpus and models. No benchmark improvement is
claimed in this state document.

## Evaluation Framework

The reusable evaluation framework is under `src/cial_knowledge_os/`:

| Module | Purpose |
|---|---|
| `benchmark_loader.py` | Loads benchmark CSV rows and optional metadata into typed benchmark records. |
| `evaluation_metrics.py` | Applies deterministic keyword, safe-failure, hallucination, and citation heuristics; aggregates and ranks experiments. |
| `evaluation_report.py` | Builds recommendations and writes the Markdown recommendation report. |
| `experiment_config.py` | Defines immutable experiment configurations, Cartesian grids, and stable configuration fingerprints. |
| `experiment_runner.py` | Runs every benchmark question for each configuration, isolates question failures, writes experiment and summary CSVs, and coordinates reports. |
| `visualization_dashboard.py` | Reads evaluation artifacts and generates a self-contained offline HTML dashboard with embedded data and no external scripts. |

`visualization.py` separately provides pandas and matplotlib diagnostics for
interactive notebook analysis. `batch_qa.py` provides general versioned batch
answer exports; it is not a substitute for ground-truth evaluation.

Evaluation is deterministic and offline, but currently heuristic. It does not
provide semantic entailment, retrieval recall against labeled relevant chunks,
or model-judged correctness.

## Benchmark Structure and Policy

The current benchmark is:

```text
data/benchmarks/cisg/
|-- benchmark_answers.csv
|-- benchmark_metadata.json
|-- cisg_questions_v1.txt
|-- README.md
`-- CHANGELOG.md
```

`benchmark_answers.csv` contains 200 questions spanning factual, definition,
procedure, comparison, executive-summary, enterprise, cross-document, and
unsupported categories. Metadata identifies it as `cisg_benchmark_v1`, version
`1.0.0`, with status `frozen`.

The benchmark dataset is immutable. Do not edit it to accommodate a new phase.
Corrections or extensions require a new version. Phase 3 and Phase 4
comparisons must retain the existing version so retrieval, answer, citation,
unsupported-question, token, and latency results remain comparable.

## Current Output Structure

The standard repository-local output roots are:

```text
outputs/
|-- batch_answers/
|-- benchmarks/
|-- evaluations/
|-- exports/
`-- logs/
```

Current batch and Phase 2 evaluation artifacts live below
`outputs/batch_answers/`. An evaluation sweep creates:

```text
outputs/batch_answers/<phase>/
|-- experiments/
|   `-- experiment_001.csv
|-- summary/
|   `-- experiment_summary.csv
`-- reports/
    |-- recommendation.md
    `-- dashboard.html
```

Some directories are created on demand and may be empty in a checkout. Later
phases extend this `outputs/` hierarchy and do not introduce a competing
top-level `artifacts/` directory.

## Phase Isolation and Frozen Notebook Policy

- Do not modify completed Phase 1 or Phase 2 notebooks.
- `01_Basic_RAG.ipynb` and
  `02_Query_Transformations_and_Context_Construction.ipynb` are frozen,
  runnable baselines.
- The Phase 2 automated-evaluation notebook is also a completed orchestration
  baseline and should remain reproducible.
- Add each new capability through a new phase notebook and reusable source
  modules.
- `notebooks/04_Reranking_and_Evidence_Selection.ipynb` is the Phase 4
  engineering and qualification notebook. It does not modify earlier notebooks.
- Preserve existing notebook imports, configuration defaults, output schemas,
  and runnable behavior unless a documented compatibility migration is
  unavoidable.
- Placeholder notebooks for later phases do not imply that those phases are
  implemented.

## Current Limitations

The current implementation has:

- no full-corpus Phase 3 or Phase 4 benchmark qualification;
- no calibrated semantic relevance/entailment evaluator;
- no retrieval-time authorization enforcement;
- no visual document understanding;
- no multimodal retrieval;
- no contradiction detection;
- no calibrated Phase 5 readiness or consensus thresholds; and
- no completed real-model Phase 5 benchmark qualification.

The repository does generate a self-contained HTML evaluation dashboard. That is
an aggregate evaluation report and remains separate from the implemented
standalone per-run Phase 3 and Phase 4 reports.

## Phase 3 and Phase 4 Qualification Status

Implemented capabilities are covered by deterministic offline tests. Remaining
qualification work is to run dense and hybrid modes against the same frozen
benchmark with the approved local corpus/models, retain both artifact sets, and
document quality, safety, token, and latency trade-offs.

Phase 4 unit, integration, serialization, compatibility, and artifact tests are
implemented. Remaining qualification work is to run the unchanged frozen
benchmark in Phase 3 Hybrid and Phase 4 Reranked Hybrid modes, retain both run
bundles, and compare answer quality, citation quality, unsupported-question
behavior, context tokens, token reduction, latency, selected/discarded chunks,
average reranker score, and evidence-strength distribution.

Visual document understanding, multimodal retrieval, and contradiction
detection are reserved for Phase 4.5. They are deferred, not partially
implemented by Phase 4.

The implemented Phase 3 output contract is:

```text
outputs/
`-- batch_answers/
    `-- 03_Hybrid_Retrieval/
        `-- run_<timestamp>/
            |-- results.csv
            |-- results.xlsx
            |-- report.html
            |-- config.json
            |-- summary.json
            |-- retrieval.json
            |-- metrics.json
            |-- logs.txt
            |-- partial_results.csv
            |-- partial_results.jsonl
            |-- partial_retrieval.jsonl
            |-- checkpoint.json
            |-- figures/
            `-- context/
```

Exact naming and collision behavior must be defined by configuration and the
`RunManager`, not repeated as ad hoc notebook logic.

The additive Phase 4 output contract is:

```text
outputs/
`-- batch_answers/
    `-- 04_Reranking_and_Evidence_Selection/
        `-- run_<timestamp>/
            |-- results.csv
            |-- results.xlsx
            |-- report.html
            |-- config.json
            |-- summary.json
            |-- retrieval.json
            |-- metrics.json
            |-- logs.txt
            |-- figures/
            `-- context/
```

`retrieval.json` is the source of truth for per-question candidate ranks,
reranker scores, selected/discarded decisions and reasons, evidence quality,
token use, latency, citations, answer, and artifact paths. CSV contains compact
machine-readable summaries. XLSX retains clickable evidence links. HTML embeds
decision visualizations and requires no CDN, external JavaScript, or network
access.

## Backward Compatibility Policy

Later phases may introduce a more efficient internal architecture, but callers,
notebooks, exports, and evaluation tooling must retain their existing contracts:

> New architecture internally. Same contracts externally.

Additive fields and adapters are preferred. If a contract must change, document
the migration, retain a compatibility path, and compare behavior against the
frozen Phase 2 baseline.

## Configuration Policy

Operational choices must not be scattered as literals through notebooks or
pipeline logic. In particular, Phase 3 and Phase 4 must not hardcode:

- paths;
- Qdrant deployment mode, URL, API key, collection, or embedded directory;
- model names;
- output folders;
- retrieval modes;
- token budgets; or
- artifact filenames.

Phase 4 additionally configures the reranker model/device/batch/local-only
policy, candidate depth, selection strategies, minimum/maximum evidence count,
reranker threshold, adaptive fallback, weak-evidence answer policy, source cap,
redundancy threshold, evidence token budget and target range, evidence strength
thresholds, minimum extractive-fallback score, weak-fallback override,
unsupported-query detection, run mode, trace mode, and large-run guard.
Phase 4 generation reliability also configures retry count, retry cooldown, and
an optional answer-word upper bound. These controls apply only to Phase 4;
earlier phase defaults and generation behavior remain unchanged.

Discard reasons are normalized as `threshold_failed`, `redundancy`,
`source_diversity_limit`, `token_budget`, `empty_text`, and
`lower_rank_fallback`. Aggregate counts are persisted in `metrics.json` and
rendered in the standalone report. Diagnostics flag candidate starvation,
greater-than-90-percent reduction, under-500-token answered contexts, and zero
average selected score with non-empty candidates.

Expose these through typed configuration or explicit function arguments, validate
them at the boundary, serialize the effective configuration with every run, and
use one resolved configuration throughout the run. Central default values are
acceptable; hidden duplicated constants are not.
# Phase 5 additive implementation

Adaptive Agentic Response Planning is implemented as an optional layer over
Phase 4. It is disabled by default, uses injected local model clients, accepts
text-only Phase 4 evidence without migration, and can preserve optional visual,
table, diagram, screenshot, scanned-region, caption, and OCR fields. Its HTML
report adds computed decision-readiness diagnostics without changing previous
reports or notebooks.

## Cross-phase execution observability

The Execution & Observability Framework is implemented under
`src/cial_knowledge_os/execution/`. Phase 4 batch execution emits run, question,
retrieval, reranking, evidence-selection, generation, checkpoint, and export
events. Shared indexing emits start/progress/completion events, preflight emits
health events, and Phase 5 mirrors its existing agent and consensus lifecycle
into EOF.

EOF writes `execution_trace.jsonl`, `progress.json`, and `progress.log` under
`outputs/runs/<run_id>/`. Rich, psutil, and nvidia-smi are optional and degrade
to plain or omitted output. The framework has no cloud dependency and no
authority over pipeline control flow. Existing artifacts and checkpoint/resume
behavior remain the source of truth for work products.

## Continuous Incremental Indexing (Implemented 2026-07-24)

FastAPI no longer scans, extracts, embeds, recreates Qdrant, or rebuilds the
corpus during ordinary startup. `backend/indexer_main.py` runs the standalone
PostgreSQL-leased worker, startup/periodic reconciliation, enterprise/personal
watchers, bounded CPU extraction, cross-document embedding batches, verified
Qdrant replacement, and atomic BM25 generation publication. Uploads, chat
attachments, committed note versions, deletes, metadata refreshes, and
confirmed admin rebuilds use the same `indexing_jobs` queue.

Qdrant server mode is the concurrent runtime requirement. Embedded mode remains
for isolated tests/notebooks. Multi-GPU scheduling beyond one worker per
explicitly assigned device remains deferred. The canonical description is
`docs/architecture/CONTINUOUS_INDEXING_ARCHITECTURE.md`.

The continuous worker defaults to eight bounded extraction workers, starts GPU
embedding at 64 chunks, adaptively grows healthy batches through 128 to 256,
and reduces the live limit on CUDA OOM. FP16 is the operational default and
falls back to FP32 on CPU. The durable status surface is available at both
`/api/index/status` and `/api/indexer/status` and includes safe CPU/GPU,
documents/hour, chunks/minute, and active-batch telemetry.
Document revisions are chunk-incremental: SHA-256 chunk hashes plus
embedding-model and chunking contract versions allow unchanged chunks to reuse
verified Qdrant vectors. A complete new version is still written and verified
before stale points are removed.

Validation on 2026-07-25 passed 495 backend tests plus 50 subtests, 59 frontend
contract tests, TypeScript checking, and the Vite production build. The existing
running frontend held `dist` open on Windows, so the identical production build
was verified in an isolated temporary output directory.

The assistant frontend now presents Connected, Validating request, Loading
published generation, Searching knowledge, Reranking sources, Generating
answer, Completed, and Failed lifecycle states. A successful partial result
identifies its degraded retrieval stage and retains Retry. User Stop,
150-second client timeout, safe terminal errors, and Retry prevent an abandoned
stream from leaving the UI in an infinite loading state.

## Real-time Assistant Health and Reliable Submission (2026-07-25)

Authenticated `GET /api/system/status` is the canonical assistant availability
contract. It measures PostgreSQL, the configured Qdrant collection, the active
published generation, durable queue/worker heartbeat, Ollama and its exact
configured model, the loaded embedding runtime, and worker GPU telemetry.
Every component includes a safe detail, UTC check timestamp, and latency; the
response also includes total latency, generation/publication timestamps, queue
depth/counts, active jobs, worker state, model names, and GPU utilization/memory
when the indexer reports them.

Overall state is `green` (all chat-critical dependencies healthy), `blue`
(indexing is active while chat remains available from the published
generation), `yellow` (non-critical degradation), or `red` (chat-critical
dependency unavailable). `chat_available`, rather than queue emptiness, is the
authoritative composer preflight gate.

The assistant header polls and expands this status as System ready, Updating
knowledge, Degraded, or Unavailable. Enter and Send share one single-flight
submission path. It refreshes the live status immediately before submission,
allows blue state, retains the draft on connection/preflight failure, clears
the draft only after the NDJSON stream is established, supports cancellation,
and keeps an explicit retry action. Event-driven progress now maps to Connected,
Validating request, Loading published generation, Searching, Reranking,
Generating, Completed, and Failed.

## Query-Priority GPU Runtime

The API and standalone indexer remain independent processes. The API now
defaults `CIAL_QUERY_EMBEDDING_DEVICE=auto`, resolves it once to `cuda:<index>`
when CUDA is available, and falls back to CPU only when CUDA is unavailable.
The same warmed BGE-M3 instance is reused for every single-vector query; it is
not loaded per request. The indexer independently retains
`CIAL_INDEXER_DEVICE=auto` for throughput-oriented batches and continues to
yield its CUDA allocation during an active chat lease.

The indexer moves its embedding model to CPU after
`CIAL_INDEXER_GPU_IDLE_RELEASE_SECONDS` when idle. Before each bounded batch it
observes a stale-safe local chat-priority lease. If chat is active, it releases
CUDA residency and waits between batches; it never kills a process or
interrupts an in-flight CUDA kernel. The model returns to its configured device
on the next batch.

Ollama generation uses `CIAL_OLLAMA_KEEP_ALIVE=30m` by default. Safe telemetry
now includes model load, prompt evaluation, first-token latency, prompt/context/
output tokens, tokens per second, total Ollama duration, GPU/VRAM samples, and
active CUDA process classifications. The indexer heartbeat reports GPU state,
active embedding jobs, chat-priority waits, residency, and process-local CUDA
allocation/reservation.

An absent, stopped, stale, or restarting indexer remains non-critical after a
valid generation has been published. API startup loads that generation directly
from PostgreSQL, Qdrant, and the BM25 snapshot. The launcher attempts to start
the indexer but does not make a missing heartbeat a chat-readiness failure.

Ollama requests `num_gpu=-1`, uses a 30-minute keep-alive, and owns CUDA
priority while the chat lease is active. The cooperative indexer releases its
embedding allocation for chat and restores CUDA on its next pending batch as
soon as the response releases the lease. That batch unloads a still-warm
Ollama runner before reclaiming CUDA; when no indexing is pending, keep-alive
can retain Gemma without blocking useful work. Keep-alive never prolongs
exclusive generation priority.
Configuration accepts `OLLAMA_KEEP_ALIVE`, `OLLAMA_GPU_PRIORITY_ENABLED`,
`OLLAMA_NUM_GPU`, and `INDEXER_GPU_COOPERATIVE_MODE`, plus their CIAL-prefixed
forms.

The administrator monitor exposes only measured generation data:
`ollama_processor_type`, Ollama/total GPU memory,
`cpu_offload_detected`, sampled average/peak GPU utilization, prompt/output
tokens, first-token latency, model-load time, and tokens/second. Ollama's live
process API does not disclose a layer count, so `gpu_layers_used` is null while
`gpu_layers_requested=-1` documents the actual request.

Generation timing is millisecond-based at the API boundary. Local elapsed
times use monotonic `perf_counter()` timestamps: first-token latency is the
first non-empty token timestamp minus generation start, and generation latency
is completion minus the same start event. Ollama `load_duration`,
`prompt_eval_duration`, and `total_duration` are native nanoseconds converted
once to milliseconds; model load therefore represents Ollama's model-load
start-to-ready interval. Output throughput uses Ollama's output count and
positive evaluation duration.

Every Ollama request clears the previous request's metrics before streaming.
The API independently recomputes generation duration and rejects negative,
non-finite, stale, or unit-inconsistent timing values, including any component
duration greater than the measured generation or request duration. Missing or
rejected metrics remain null and the console renders `Unavailable`. The
previously observed 1,758,803 ms first-token value alongside a 24,179 ms
generation was invalid telemetry, not generation behavior, and is now rejected
at both backend and presentation boundaries.

Live verification on the RTX 5070 Ti Laptop GPU (12,227 MiB reported VRAM)
showed `gemma3:12b` at `100% GPU` in `ollama ps`, 7,672.1 MiB attributed to
the Ollama model, no CPU offload, and 100% sampled peak generation utilization.
A cold one-word probe completed in 16.0 seconds including a 15.3-second model
load; the immediately repeated warm probe completed in 1.6 seconds at 33.59
tokens/second. These probes validate the generation runtime and keep-alive,
not the latency of retrieval or a full authenticated chat request.

## Standalone Indexer CUDA Verification (2026-07-26)

The continuous indexer resolves `CIAL_INDEXER_DEVICE=auto` inside its own
process. The resolved `cuda:<index>` value is retained across the intentional
idle/chat release cycle; the literal `auto` value is not used as a restore
target. BGE-M3 must be on CUDA before `model.encode()` whenever the installed
PyTorch runtime reports CUDA available. CPU fallback is permitted only when
CUDA is genuinely unavailable.

The corrected runtime logs configured/actual device, CUDA availability and
device name, PyTorch/CUDA build, model device/dtype, allocated/reserved bytes,
and real per-batch size/device/memory/duration. A CUDA configuration/actual
device mismatch produces an actionable warning and stops that indexing batch
instead of silently completing it on CPU.

Live verification used the repository virtual environment with
PyTorch `2.13.0+cu132`, CUDA build 13.2, and the NVIDIA RTX 5070 Ti Laptop GPU.
After an intentional CPU/idle release, the production embedding service
restored BGE-M3 to `cuda:0` and encoded 256 chunks into 1024-dimensional vectors
in 4.23 seconds. The encode call reported float16 model parameters, 1.14 GiB
allocated before and 1.17 GiB after, while 21 independent `nvidia-smi` samples
observed 100% peak utilization and 5,414 MiB peak total device memory.
Validation passed 510 backend tests plus 50 subtests, 59 frontend contract
tests, TypeScript checking, and the production frontend build.

Troubleshooting order:

1. Run CUDA checks with the repository `.venv`, not a global Python.
2. Confirm `torch.version.cuda`, `torch.cuda.is_available()`, device count, and
   device name.
3. Inspect the worker heartbeat's configured device, actual device, model
   status, GPU residency, and last batch telemetry.
4. Confirm an active batch—not extraction, Qdrant writing, chunk reuse, or the
   post-idle period—is being observed in `nvidia-smi`.
5. Treat configured CUDA with actual CPU as an indexing failure; do not infer
   success from the startup device label alone.

## Phase 2 Retrieval Infrastructure (2026-07-26)

The API loads BGE-M3 once, performs a discarded startup encode, verifies the
actual device/dtype, marks the model warmed, and reuses that same object for
queries. Query telemetry now records real monotonic start/completion boundaries,
duration, device, dtype, model state, and `model_reused` cache status. No query
embedding vectors are cached.

Qdrant server startup idempotently verifies payload indexes for repository,
workspace, organization, document/version, publication, storage scope, owner,
department, folder, visibility, lifecycle, relative-path, and note fields.
The query filter remains unchanged: SQL/RBAC resolves accessible paths and the
dense request applies the same published-version/path/repository predicates.
`qdrant_search_latency_ms` measures the complete filtered Qdrant request.
Qdrant does not expose independent server-side filter evaluation time through
this API, so `qdrant_filter_latency_ms` remains unavailable rather than being
fabricated.

A bounded in-memory retrieval-result cache stores only fused retrieval
candidates and modality rankings. It never stores an LLM answer. Keys bind the
normalized-query hash, active published generation, effective workspace/path
scope, and a fingerprint of the resolved principal, roles, permissions,
departments, groups, organization, and authentication state. Generation
activation clears all entries; a changed permission fingerprint removes every
entry for that principal. Hits return defensive copies in the original order,
then execute the unchanged reranker, evidence selector, context/citation
builder, prompt, and generation path.

Live Qdrant inspection found all declared payload indexes ready on the
472,126-point `cial_phase4` collection. A workspace-and-version filtered
10-candidate query measured 1,151 ms on its first cold access and 2.9-5.1 ms
on four warm repetitions. A full authenticated published-generation cache
probe could not be run from the validation shell because that shell had no
active PostgreSQL generation pointer; the cache hit target is therefore
covered by deterministic pipeline tests, not claimed as a live end-to-end
measurement. CUDA query-embedding timing was also not duplicated in a new
process while the workstation reported 11,650/12,227 MiB already allocated
across Ollama and two Python CUDA processes.
