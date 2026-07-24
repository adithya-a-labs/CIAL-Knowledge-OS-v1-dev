# BACKEND_MIGRATION_MANIFEST

Audit basis: repository checkout inspected on 2026-07-08.  
Output mode: analysis only; this manifest was generated from repository inspection.

## 1. Executive Summary

The migration target is the deterministic backend path implemented through the Phase 4 codebase plus the already-shipped multi-format/OCR/file-readiness stack that the repository now uses operationally as a deterministic "Phase 4.5" baseline. The code that matters is concentrated in `src/cial_knowledge_os`, the Phase 4 runner scripts, the benchmark assets, and the canonical corpus contract rooted at `data/files/`.

Do migrate the deterministic ingestion, chunking, embeddings, BM25, hybrid retrieval, RRF, reranking, evidence selection, context building, grounded generation, citations, exports, incremental indexing, OCR, run/reporting, and observability layers.

Do not migrate Phase 5 agentic work. Do not migrate generated runtime state such as Qdrant stores, BM25 caches, output bundles, or the current `document_manifest.json`. Treat `data/files/` as a required runtime corpus root, but not as source code; large corpora should be carried separately from the new integrated application repository.

## 2. Repository Overview

| Path | Status | Notes |
|---|---|---|
| `src/cial_knowledge_os/` | Required | Main backend package; mixed runtime, evaluation, and Phase 5 code. |
| `scripts/` | Mixed | Contains required Phase 4 runner plus optional ops scripts and Phase 5 exclusions. |
| `docs/` | Mixed | Contains required architecture/operations docs plus Phase 5 docs to exclude. |
| `data/` | Mixed | Contains required benchmark assets, optional QA inputs, canonical corpus root contract, and generated state to exclude. |
| `notebooks/` | Mixed | Contains required reference notebooks for Phases 1-4, optional deterministic multimodal test notebook, placeholders, and Phase 5 notebook. |
| `tests/` | Development Only | Strongly recommended to migrate non-Phase 5 tests. |
| `references/` | Optional | Learning notebooks only; not implementation source. |
| `project-docs/` | Optional | Historical screenshots only. |
| `documents/` | Ignore | Empty placeholder folders; not used by runtime. |
| `frontend/` | Ignore | Empty placeholder. |
| `.venv/` | Ignore | Local environment. |
| `.pytest_cache/` | Ignore | Generated. |
| `__pycache__/` | Ignore | Generated. |
| `.git/` | Ignore | Repository metadata. |
| `.agents/` | Ignore | Tooling metadata. |

### Top-level files

| File | Status | Notes |
|---|---|---|
| `pyproject.toml` | Required | Packaging metadata and package-data inclusion. |
| `requirements.txt` | Required | Current pinned dependency source of truth, but contains non-production extras. |
| `README.md` | Required | Most complete operational overview. |
| `docker-compose.qdrant.yml` | Required | Required if preserving local Qdrant server mode. |
| `.gitignore` | Required | Important runtime/generated-state exclusions. |
| `.gitattributes` | Optional | Useful for line ending consistency. |
| `.vscode/settings.json` | Optional | Local editor convenience only. |
| `download_models.py` | Development Only | One-time staging helper; currently misaligned with the Phase 4 default reranker. |
| `pytorch_test.py` | Development Only | GPU probe only. |
| `project_structure.txt` | Deprecated | Stale inventory; no longer reflects current package layout. |
| `LICENSE` | Ignore | Empty file. |
| `oss_llm_comparison.md` | Ignore | Empty file. |

## 3. Required Folders

The production engine is mostly file-based inside one package rather than split into clean feature folders. These are the runtime groups that must be migrated.

| Engine Area | Files / Paths | Status |
|---|---|---|
| Core pipeline base | `rag_pipeline.py`, `phase2_pipeline.py`, `phase3_pipeline.py`, `phase4_pipeline.py` | Required |
| Recursive discovery, loaders, normalization | `loaders.py`, `file_formats.py`, `metadata.py`, `incremental_index.py` | Required |
| OCR | `ocr/` | Required |
| Chunking | `chunking.py` | Required |
| Embeddings | `embeddings.py` | Required |
| Vector index / Qdrant | `vectorstore.py` | Required |
| Retrieval | `retrieval.py`, `retrievers.py`, `retrieval_postprocessing.py` | Required |
| Query rewriting / transformations | `query_transformations.py` | Required |
| Fusion / RRF | `fusion.py` | Required |
| Reranking | `reranker.py` | Required |
| Evidence selection / quality | `evidence_selector.py`, `evidence_quality.py` | Required |
| Context builder | `context_builder.py` | Required |
| Generation | `llm.py` | Required |
| Citations / citation links | `citations.py`, `citation_links.py` | Required |
| Exports / run artifacts | `batch_qa.py`, `phase3_reporting.py`, `phase4_reporting.py`, `run_manager.py`, `phase4_checkpoint.py` | Required |
| Phase runners / orchestration | `phase3_runner.py`, `phase4_runner.py` | Required |
| Traces / diagnostics used by artifacts | `retrieval_trace.py`, `phase4_trace.py` | Required |
| Configuration / token budgets / logging | `config.py`, `token_budget.py`, `logging_config.py` | Required |
| Packaged tokenizer asset | `assets/` | Required |
| Execution observability | `execution/` | Required for current batch workflow parity |
| Infrastructure health | `infra/` | Optional but recommended |

### Optional or development-only package areas

| Path | Status | Notes |
|---|---|---|
| `benchmark_loader.py`, `evaluation_metrics.py`, `evaluation_report.py`, `experiment_config.py`, `experiment_runner.py` | Optional | Needed for benchmark and regression workflows, not for answer-serving runtime. |
| `benchmarking.py` | Development Only | Notebook/helper timing utilities. |
| `visualization.py`, `trace_visualization.py`, `visualization_dashboard.py` | Development Only | Diagnostics and offline dashboards. |
| `agents/` | Experimental | Phase 5 only. DO NOT MIGRATE. |
| `orchestration/` | Experimental | Phase 5 only. DO NOT MIGRATE. |
| `live/` | Experimental | Phase 5 live dashboard only. DO NOT MIGRATE. |
| `reporting/` | Experimental | Phase 5 HTML/reporting only. DO NOT MIGRATE. |

## 4. Required Files

### Runtime-critical package files

- `src/cial_knowledge_os/__init__.py`
- `src/cial_knowledge_os/config.py`
- `src/cial_knowledge_os/rag_pipeline.py`
- `src/cial_knowledge_os/phase2_pipeline.py`
- `src/cial_knowledge_os/phase3_pipeline.py`
- `src/cial_knowledge_os/phase4_pipeline.py`
- `src/cial_knowledge_os/phase3_runner.py`
- `src/cial_knowledge_os/phase4_runner.py`
- `src/cial_knowledge_os/phase4_checkpoint.py`
- `src/cial_knowledge_os/run_manager.py`
- `src/cial_knowledge_os/loaders.py`
- `src/cial_knowledge_os/file_formats.py`
- `src/cial_knowledge_os/ocr/base_ocr.py`
- `src/cial_knowledge_os/ocr/ocr_factory.py`
- `src/cial_knowledge_os/ocr/tesseract_ocr.py`
- `src/cial_knowledge_os/chunking.py`
- `src/cial_knowledge_os/embeddings.py`
- `src/cial_knowledge_os/vectorstore.py`
- `src/cial_knowledge_os/incremental_index.py`
- `src/cial_knowledge_os/retrieval.py`
- `src/cial_knowledge_os/retrievers.py`
- `src/cial_knowledge_os/retrieval_postprocessing.py`
- `src/cial_knowledge_os/query_transformations.py`
- `src/cial_knowledge_os/fusion.py`
- `src/cial_knowledge_os/reranker.py`
- `src/cial_knowledge_os/evidence_selector.py`
- `src/cial_knowledge_os/evidence_quality.py`
- `src/cial_knowledge_os/context_builder.py`
- `src/cial_knowledge_os/llm.py`
- `src/cial_knowledge_os/citations.py`
- `src/cial_knowledge_os/citation_links.py`
- `src/cial_knowledge_os/batch_qa.py`
- `src/cial_knowledge_os/phase3_reporting.py`
- `src/cial_knowledge_os/phase4_reporting.py`
- `src/cial_knowledge_os/retrieval_trace.py`
- `src/cial_knowledge_os/phase4_trace.py`
- `src/cial_knowledge_os/token_budget.py`
- `src/cial_knowledge_os/logging_config.py`
- `src/cial_knowledge_os/metadata.py`
- `src/cial_knowledge_os/assets/9b5ad71b2ce5302211f9c61530b329a4922fc6a4`
- `src/cial_knowledge_os/assets/README.md`
- `src/cial_knowledge_os/execution/*`

### Top-level required files

- `pyproject.toml`
- `requirements.txt`
- `README.md`
- `docker-compose.qdrant.yml`
- `.gitignore`

### Important caution

`src/cial_knowledge_os/__init__.py` currently exports Phase 5 symbols. If the new repo excludes Phase 5 files, this initializer cannot be copied blindly without follow-up pruning in the destination repo.

## 5. Optional Files

| Path | Status | Notes |
|---|---|---|
| `scripts/check_qdrant_health.py` | Optional | Useful ops script. |
| `scripts/start_qdrant.bat` | Optional | Convenience wrapper. |
| `scripts/stop_qdrant.bat` | Optional | Convenience wrapper. |
| `scripts/migrate_embedded_qdrant_to_server.py` | Optional | Useful if preserving existing embedded collections. |
| `docs/AUTOMATED_EVALUATION.md` | Optional | Evaluation workflow reference. |
| `docs/BATCH_QA_EXPORT.md` | Optional | Export contract reference. |
| `docs/deployment/local_docker.md` | Optional | Local deployment/backup reference. |
| `docs/deployment/offline_release_plan.md` | Optional | Release packaging guidance. |
| `data/manual_qa/*.txt` | Optional | Useful QA question packs. |
| `data/files/Test/` | Optional | Good deterministic mixed-format regression corpus. |
| `references/*.ipynb` | Optional | Learning-only references. |
| `project-docs/screenshots/` | Optional | Historical screenshots only. |

## 6. Documentation to Migrate

### Required documentation

- `README.md`
- `docs/CURRENT_STATE.md`
- `docs/PROJECT_REQUIREMENTS.md`
- `docs/qdrant_backend.md`
- `docs/execution_observability.md`

### Strongly recommended documentation

- `docs/AUTOMATED_EVALUATION.md`
- `docs/BATCH_QA_EXPORT.md`
- `docs/PROJECT_RULES.md`
- `docs/NOTEBOOK_GUIDELINES.md`
- `docs/deployment/local_docker.md`
- `docs/deployment/offline_release_plan.md`

### Optional planning/reference documentation

- `docs/ROADMAP.md`
- `project-docs/screenshots/*`
- `references/*.ipynb`

### Notebooks to keep as documentation/reference

| Notebook | Status | Notes |
|---|---|---|
| `notebooks/01_Basic_RAG.ipynb` | Optional | Frozen Phase 1 reference. |
| `notebooks/02_Query_Transformations_and_Context_Construction.ipynb` | Optional | Frozen Phase 2 reference. |
| `notebooks/03_Hybrid_Retrieval.ipynb` | Optional | Phase 3 reference. |
| `notebooks/04_Reranking_and_Evidence_Selection.ipynb` | Optional | Best reference notebook for deterministic production path. |
| `notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb` | Optional | Deterministic mixed-format/OCR test workflow; useful if preserving current "Phase 4.5" validation path. |
| `notebooks/00_Setup_Check.ipynb` | Development Only | Environment probe only. |

## 7. Scripts to Migrate

| Script | Status | Notes |
|---|---|---|
| `scripts/run_phase4_batch.py` | Required | Main operational runner for deterministic backend. |
| `scripts/run_phase4_interactive.py` | Optional | Thin compatibility wrapper. |
| `scripts/check_qdrant_health.py` | Optional | Health inspection. |
| `scripts/start_qdrant.bat` | Optional | Local convenience. |
| `scripts/stop_qdrant.bat` | Optional | Local convenience. |
| `scripts/migrate_embedded_qdrant_to_server.py` | Optional | One-time backend migration utility. |
| `scripts/migrate_pdf_to_files.py` | Deprecated | Only needed if legacy `data/pdf/` still exists and must be migrated. |
| `scripts/ocr_smoke_test.py` | Development Only | OCR preflight helper. |
| `download_models.py` | Development Only | One-time staging helper; not aligned with current default reranker. |
| `pytorch_test.py` | Development Only | GPU smoke check. |

## 8. Configuration Files

| File | Status | Notes |
|---|---|---|
| `pyproject.toml` | Required | Packaging and package-data inclusion. |
| `requirements.txt` | Required | Current pinned dependencies. |
| `docker-compose.qdrant.yml` | Required | Needed for local Qdrant server mode. |
| `.gitignore` | Required | Must preserve generated-state exclusions. |
| `.gitattributes` | Optional | Recommended for notebook/script line endings. |
| `.vscode/settings.json` | Ignore | User-local IDE setting only. |
| `.env.example` | Missing | No environment template exists in this repo. |

### Actual configuration sources in current backend

- Typed defaults live in `src/cial_knowledge_os/config.py`.
- Operator-facing run settings live in the `USER CONFIGURATION` block in `scripts/run_phase4_batch.py`.
- Runtime env vars actually used by code are minimal:
  - `TRANSFORMERS_OFFLINE`
  - `HF_HUB_OFFLINE`
  - `TESSERACT_CMD`
  - internal `TIKTOKEN_CACHE_DIR` handling in `token_budget.py`

## 9. Python Dependency Files

### Source-of-truth dependency file

- `requirements.txt`

### Deterministic Phase 4 / 4.5 runtime dependencies

- `docling`
- `httpx`
- `langchain-core`
- `langchain-ollama`
- `langchain-text-splitters`
- `matplotlib`
- `numpy`
- `ollama`
- `openpyxl`
- `pandas`
- `Pillow`
- `PyMuPDF`
- `pytesseract`
- `qdrant-client`
- `rank-bm25`
- `sentence-transformers`
- `tiktoken`
- `torch`

### Optional ops/developer dependencies already in `requirements.txt`

- `psutil`

### Phase 5 / excluded dependencies still present in `requirements.txt`

- `fastapi`
- `uvicorn`

### Audit note

`requirements.txt` is monolithic. It mixes deterministic backend, evaluation/reporting, observability, and Phase 5 live-dashboard dependencies. It is the correct source file to carry forward, but not the correct minimal subset for a Phase 4-only destination repo.

## 10. External Runtime Requirements

- Python `>=3.11`
- Local Ollama service running
- Default generation model installed locally: `gemma3:12b`
- Local Hugging Face cache containing embedding model `BAAI/bge-m3`
- Local Hugging Face cache containing reranker model `cross-encoder/ms-marco-MiniLM-L-6-v2` for strict offline use
- Tesseract OCR binary installed locally and reachable via `PATH` or `TESSERACT_CMD`
- Docker Engine / Docker Compose if using Qdrant server mode
- Local Qdrant, either:
  - embedded mode via `qdrant-client`, or
  - server mode via `docker-compose.qdrant.yml`
- Optional GPU/CUDA for embeddings and reranking acceleration
- Optional `nvidia-smi` for telemetry only
- Expected offline flags: `TRANSFORMERS_OFFLINE=1`, `HF_HUB_OFFLINE=1`

### Qdrant-specific notes

- Config default collection family for deterministic baseline is `cial_phase4`.
- `data/qdrant/` holds embedded collections and is generated state.
- `data/qdrant_server/` holds server-side data and is generated state.
- The current `document_manifest.json` is collection-bound and must not be reused blindly.

## 11. Files to Explicitly Exclude

| Path | Status | Reason |
|---|---|---|
| `.venv/` | Ignore | Local environment. |
| `.pytest_cache/` | Ignore | Generated. |
| `__pycache__/` | Ignore | Generated. |
| `.git/` | Ignore | Repository metadata. |
| `.agents/` | Ignore | Tooling metadata. |
| `outputs/` | Ignore | Generated reports and run bundles. |
| `data/qdrant/` | Ignore | Generated embedded vector state. |
| `data/qdrant_server/` | Ignore | Generated server vector state. |
| `data/bm25/` | Ignore | Generated BM25 caches. |
| `data/chunks/` | Ignore | Generated placeholder/runtime area. |
| `data/embeddings/` | Ignore | Generated placeholder/runtime area. |
| `data/processed/` | Ignore | Generated placeholder/runtime area. |
| `data/raw/` | Ignore | Runtime scratch area. |
| `data/indexes/document_manifest.json` | Ignore | Generated incremental-index state; current file points to `cial_phase4_multimodal_test` and `data/files/Test`. |
| `data/pdf/` | Deprecated | Legacy migration source only; runtime no longer ingests from here. |
| `documents/` | Ignore | Empty placeholders. |
| `frontend/` | Ignore | Empty placeholder. |
| `project_structure.txt` | Deprecated | Stale. |
| `LICENSE` | Ignore | Empty. |
| `oss_llm_comparison.md` | Ignore | Empty. |
| `scripts/fix_notebook_cell.py` | Ignore | One-off notebook repair script. |
| `scripts/validate_notebook_cells.py` | Ignore | One-off notebook validation script. |
| `notebooks/04_Reranking.ipynb` | Ignore | Empty placeholder. |
| `notebooks/05_Agentic_RAG.ipynb` | Ignore | Empty placeholder. |
| `notebooks/06_Evaluation.ipynb` | Ignore | Empty placeholder. |
| `notebooks/Final_Enterprise_RAG.ipynb` | Ignore | Empty placeholder. |

## 12. Experimental / Phase 5 Exclusions

These are explicit DO NOT MIGRATE items.

- `src/cial_knowledge_os/agents/`
- `src/cial_knowledge_os/orchestration/`
- `src/cial_knowledge_os/live/`
- `src/cial_knowledge_os/reporting/`
- `scripts/run_phase5_batch.py`
- `docs/phase5.md`
- `docs/phase5-live-command-center.md`
- `notebooks/05_Agentic_Response_Planning.ipynb`
- `tests/test_phase5.py`
- `tests/test_phase5_cli.py`
- `tests/test_phase5_live.py`
- `tests/test_phase5_reporting.py`

### Development-only tests worth migrating

These are not runtime requirements, but they should come forward if the new repo wants regression parity with the deterministic backend:

- `tests/test_batch_qa.py`
- `tests/test_corpus_architecture.py`
- `tests/test_evaluation_framework.py`
- `tests/test_execution_observability.py`
- `tests/test_file_formats.py`
- `tests/test_incremental_index.py`
- `tests/test_infrastructure_hardening.py`
- `tests/test_ocr_imports.py`
- `tests/test_phase2.py`
- `tests/test_phase2_regressions.py`
- `tests/test_phase2_visualization.py`
- `tests/test_phase3_artifacts.py`
- `tests/test_phase3_retrieval.py`
- `tests/test_phase4.py`
- `tests/test_phase4_cli.py`
- `tests/test_phase4_reporting.py`
- `tests/test_phase4_runner_limits.py`
- `tests/test_qdrant_backends.py`
- `tests/test_sample_documents.py`

## 13. Risks During Migration

- Repository naming is inconsistent with runtime reality. The codebase ships deterministic multi-format/OCR/file-readiness behavior, but `docs/ROADMAP.md` and `docs/CURRENT_STATE.md` still describe Phase 4.5 as deferred. Treat the code surface, not the roadmap label, as authoritative for migration scope.
- `src/cial_knowledge_os/__init__.py` exports Phase 5 symbols. Excluding Phase 5 files without adjusting the destination initializer will break `from cial_knowledge_os import *` and related imports.
- `requirements.txt` includes Phase 5/live-dashboard dependencies not needed for the deterministic backend.
- `data/indexes/document_manifest.json` is not portable state. The current file is bound to collection `cial_phase4_multimodal_test` and corpus root `data/files/Test`; reusing it in the new repo would corrupt incremental indexing assumptions.
- `scripts/run_phase4_batch.py` is the real operator surface, but it encodes configuration directly in Python rather than through `.env.example` or a dedicated config file.
- The code repo and the knowledge corpus are separate concerns. Migrating code without a clear plan for `data/files/` will produce an empty corpus.
- The current top-level `.gitignore` ignores `data/files/`, even though tracked corpus files exist in this checkout. The new repo must decide whether corpus content lives in Git, Git LFS, or mounted storage.
- No lockfile or offline wheelhouse is present. `requirements.txt` is pinned, but release reproducibility still depends on external packaging discipline.
- Phase 4 script defaults and config defaults differ: the runner script defaults to Qdrant server mode, while `Phase4Config` defaults to embedded mode.
- `download_models.py` stages `BAAI/bge-reranker-v2-m3`, while the default Phase 4 code path expects `cross-encoder/ms-marco-MiniLM-L-6-v2`. It should not be treated as authoritative baseline setup.

## 14. Recommended Folder Structure for the New Integrated Repository

```text
<integrated-repo>/
|-- apps/
|   `-- web/                         # new frontend
|-- services/
|   `-- knowledge-engine/
|       |-- src/
|       |   `-- cial_knowledge_os/
|       |-- scripts/
|       |-- tests/
|       |-- docs/
|       |   `-- backend/
|       |-- pyproject.toml
|       |-- requirements.txt
|       |-- docker-compose.qdrant.yml
|       |-- README.md
|       |-- .gitignore
|       `-- .gitattributes
|-- data/
|   |-- benchmarks/
|   |   `-- cisg/
|   |-- manual_qa/
|   |-- test_corpus/                 # optional copy of data/files/Test
|   |-- files/                       # canonical corpus root; preferably mounted, not committed
|   |-- indexes/                     # generated, gitignored
|   |-- bm25/                        # generated, gitignored
|   |-- qdrant/                      # generated, gitignored
|   |-- qdrant_server/               # generated, gitignored
|   `-- outputs/                     # generated, gitignored
`-- docs/
    `-- architecture/                # full-stack integration docs
```

### Structure principles

- Keep backend code under a dedicated service package.
- Keep benchmark assets in-repo.
- Keep large enterprise corpora outside normal source control where possible.
- Preserve the `data/files/` contract even if the physical storage is external.
- Keep generated index and output state out of source control.

## 15. Final Migration Checklist

- Copy the deterministic Phase 1-4 runtime modules from `src/cial_knowledge_os/`.
- Copy `ocr/`, `execution/`, `assets/`, and all Phase 3/4 reporting/export files.
- Copy `pyproject.toml`, `requirements.txt`, `README.md`, `docker-compose.qdrant.yml`, and `.gitignore`.
- Copy `scripts/run_phase4_batch.py`; optionally copy Qdrant health/start/stop/migration utilities.
- Copy `data/benchmarks/cisg/`.
- Optionally copy `data/manual_qa/`.
- Optionally copy `data/files/Test/` as a regression corpus.
- Do not copy `data/qdrant/`, `data/qdrant_server/`, `data/bm25/`, `outputs/`, or `data/indexes/document_manifest.json`.
- Do not copy Phase 5 package folders, scripts, docs, tests, or notebook.
- Decide how the destination repo will host the canonical `data/files/` corpus: mounted storage, separate repo, or managed artifact store.
- Rebuild the manifest, BM25 cache, and Qdrant collections fresh in the destination repo.
- Prune Phase 5 symbols from the destination `__init__.py` if Phase 5 files are excluded.
- Split or annotate dependencies in the destination repo so deterministic runtime deps are separated from Phase 5/live-dashboard extras.
- Preserve and migrate the non-Phase 5 tests if regression coverage matters.
- Validate the migrated backend with:
  - benchmark assets under `data/benchmarks/cisg/`
  - a small manual QA question file
  - OCR preflight
  - embedded Qdrant and server Qdrant smoke paths
- Treat `data/pdf/` only as a one-time legacy migration source, not as runtime input.

## 16. Exact File Migration Inventory

This is the concrete file-level migration set for the deterministic backend baseline.

### Top-level files

- `pyproject.toml`
- `requirements.txt`
- `README.md`
- `docker-compose.qdrant.yml`
- `.gitignore`
- `.gitattributes`

### Core package files

- `src/cial_knowledge_os/__init__.py`
- `src/cial_knowledge_os/batch_qa.py`
- `src/cial_knowledge_os/chunking.py`
- `src/cial_knowledge_os/citations.py`
- `src/cial_knowledge_os/citation_links.py`
- `src/cial_knowledge_os/config.py`
- `src/cial_knowledge_os/context_builder.py`
- `src/cial_knowledge_os/embeddings.py`
- `src/cial_knowledge_os/evidence_quality.py`
- `src/cial_knowledge_os/evidence_selector.py`
- `src/cial_knowledge_os/file_formats.py`
- `src/cial_knowledge_os/fusion.py`
- `src/cial_knowledge_os/incremental_index.py`
- `src/cial_knowledge_os/llm.py`
- `src/cial_knowledge_os/loaders.py`
- `src/cial_knowledge_os/logging_config.py`
- `src/cial_knowledge_os/metadata.py`
- `src/cial_knowledge_os/phase2_pipeline.py`
- `src/cial_knowledge_os/phase3_pipeline.py`
- `src/cial_knowledge_os/phase3_reporting.py`
- `src/cial_knowledge_os/phase3_runner.py`
- `src/cial_knowledge_os/phase4_checkpoint.py`
- `src/cial_knowledge_os/phase4_pipeline.py`
- `src/cial_knowledge_os/phase4_reporting.py`
- `src/cial_knowledge_os/phase4_runner.py`
- `src/cial_knowledge_os/phase4_trace.py`
- `src/cial_knowledge_os/query_transformations.py`
- `src/cial_knowledge_os/rag_pipeline.py`
- `src/cial_knowledge_os/reranker.py`
- `src/cial_knowledge_os/retrieval.py`
- `src/cial_knowledge_os/retrieval_postprocessing.py`
- `src/cial_knowledge_os/retrieval_trace.py`
- `src/cial_knowledge_os/retrievers.py`
- `src/cial_knowledge_os/run_manager.py`
- `src/cial_knowledge_os/token_budget.py`
- `src/cial_knowledge_os/vectorstore.py`

### OCR package

- `src/cial_knowledge_os/ocr/__init__.py`
- `src/cial_knowledge_os/ocr/base_ocr.py`
- `src/cial_knowledge_os/ocr/ocr_factory.py`
- `src/cial_knowledge_os/ocr/tesseract_ocr.py`

### Execution and observability package

- `src/cial_knowledge_os/execution/__init__.py`
- `src/cial_knowledge_os/execution/console.py`
- `src/cial_knowledge_os/execution/events.py`
- `src/cial_knowledge_os/execution/event_bus.py`
- `src/cial_knowledge_os/execution/json_trace.py`
- `src/cial_knowledge_os/execution/manager.py`
- `src/cial_knowledge_os/execution/metrics.py`
- `src/cial_knowledge_os/execution/progress.py`
- `src/cial_knowledge_os/execution/renderers.py`
- `src/cial_knowledge_os/execution/schemas.py`
- `src/cial_knowledge_os/execution/telemetry.py`

### Infrastructure helpers

- `src/cial_knowledge_os/infra/__init__.py`
- `src/cial_knowledge_os/infra/preflight.py`
- `src/cial_knowledge_os/infra/qdrant_health.py`
- `src/cial_knowledge_os/infra/system_health.py`

### Packaged tokenizer asset

- `src/cial_knowledge_os/assets/9b5ad71b2ce5302211f9c61530b329a4922fc6a4`
- `src/cial_knowledge_os/assets/README.md`

### Required runner and ops scripts

- `scripts/run_phase4_batch.py`
- `scripts/run_phase4_interactive.py`
- `scripts/check_qdrant_health.py`
- `scripts/migrate_embedded_qdrant_to_server.py`
- `scripts/start_qdrant.bat`
- `scripts/stop_qdrant.bat`

### Required documentation files

- `docs/CURRENT_STATE.md`
- `docs/PROJECT_REQUIREMENTS.md`
- `docs/qdrant_backend.md`
- `docs/execution_observability.md`

### Strongly recommended supporting documentation

- `docs/AUTOMATED_EVALUATION.md`
- `docs/BATCH_QA_EXPORT.md`
- `docs/PROJECT_RULES.md`
- `docs/NOTEBOOK_GUIDELINES.md`
- `docs/deployment/local_docker.md`
- `docs/deployment/offline_release_plan.md`

### Benchmark assets

- `data/benchmarks/cisg/README.md`
- `data/benchmarks/cisg/CHANGELOG.md`
- `data/benchmarks/cisg/benchmark_answers.csv`
- `data/benchmarks/cisg/benchmark_metadata.json`
- `data/benchmarks/cisg/cisg_questions_v1.txt`

### Recommended manual QA assets

- `data/manual_qa/airport_operations_questions.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_10_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_200_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Stress_Test_500_Questions.txt`
- `data/manual_qa/CIAL_Multimodal_Test_Questions.txt`
- `data/manual_qa/cybersecurity_questions.txt`
- `data/manual_qa/easa_qns.txt`
- `data/manual_qa/phase4_hal.txt`
- `data/manual_qa/phase4_questions.txt`
- `data/manual_qa/phase4_questions_small.txt`
- `data/manual_qa/smoke_questions.txt`

### Optional regression corpus to migrate for deterministic validation

- `data/files/Test/`

### Optional notebooks to migrate as engineering reference

- `notebooks/01_Basic_RAG.ipynb`
- `notebooks/02_Query_Transformations_and_Context_Construction.ipynb`
- `notebooks/03_Hybrid_Retrieval.ipynb`
- `notebooks/04_Reranking_and_Evidence_Selection.ipynb`
- `notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb`

### Optional non-Phase-5 tests to migrate

- `tests/test_batch_qa.py`
- `tests/test_corpus_architecture.py`
- `tests/test_evaluation_framework.py`
- `tests/test_execution_observability.py`
- `tests/test_file_formats.py`
- `tests/test_incremental_index.py`
- `tests/test_infrastructure_hardening.py`
- `tests/test_ocr_imports.py`
- `tests/test_phase2.py`
- `tests/test_phase2_regressions.py`
- `tests/test_phase2_visualization.py`
- `tests/test_phase3_artifacts.py`
- `tests/test_phase3_retrieval.py`
- `tests/test_phase4.py`
- `tests/test_phase4_cli.py`
- `tests/test_phase4_reporting.py`
- `tests/test_phase4_runner_limits.py`
- `tests/test_qdrant_backends.py`
- `tests/test_sample_documents.py`

## 17. Exact Destination Paths in the New Integrated Repository

This section maps the files from Section 16 into the proposed integrated repository structure.

### Place these in `services/knowledge-engine/`

- `pyproject.toml` -> `services/knowledge-engine/pyproject.toml`
- `requirements.txt` -> `services/knowledge-engine/requirements.txt`
- `README.md` -> `services/knowledge-engine/README.md`
- `docker-compose.qdrant.yml` -> `services/knowledge-engine/docker-compose.qdrant.yml`
- `.gitignore` -> `services/knowledge-engine/.gitignore`
- `.gitattributes` -> `services/knowledge-engine/.gitattributes`

### Place these in `services/knowledge-engine/src/cial_knowledge_os/`

- `src/cial_knowledge_os/__init__.py` -> `services/knowledge-engine/src/cial_knowledge_os/__init__.py`
- `src/cial_knowledge_os/batch_qa.py` -> `services/knowledge-engine/src/cial_knowledge_os/batch_qa.py`
- `src/cial_knowledge_os/chunking.py` -> `services/knowledge-engine/src/cial_knowledge_os/chunking.py`
- `src/cial_knowledge_os/citations.py` -> `services/knowledge-engine/src/cial_knowledge_os/citations.py`
- `src/cial_knowledge_os/citation_links.py` -> `services/knowledge-engine/src/cial_knowledge_os/citation_links.py`
- `src/cial_knowledge_os/config.py` -> `services/knowledge-engine/src/cial_knowledge_os/config.py`
- `src/cial_knowledge_os/context_builder.py` -> `services/knowledge-engine/src/cial_knowledge_os/context_builder.py`
- `src/cial_knowledge_os/embeddings.py` -> `services/knowledge-engine/src/cial_knowledge_os/embeddings.py`
- `src/cial_knowledge_os/evidence_quality.py` -> `services/knowledge-engine/src/cial_knowledge_os/evidence_quality.py`
- `src/cial_knowledge_os/evidence_selector.py` -> `services/knowledge-engine/src/cial_knowledge_os/evidence_selector.py`
- `src/cial_knowledge_os/file_formats.py` -> `services/knowledge-engine/src/cial_knowledge_os/file_formats.py`
- `src/cial_knowledge_os/fusion.py` -> `services/knowledge-engine/src/cial_knowledge_os/fusion.py`
- `src/cial_knowledge_os/incremental_index.py` -> `services/knowledge-engine/src/cial_knowledge_os/incremental_index.py`
- `src/cial_knowledge_os/llm.py` -> `services/knowledge-engine/src/cial_knowledge_os/llm.py`
- `src/cial_knowledge_os/loaders.py` -> `services/knowledge-engine/src/cial_knowledge_os/loaders.py`
- `src/cial_knowledge_os/logging_config.py` -> `services/knowledge-engine/src/cial_knowledge_os/logging_config.py`
- `src/cial_knowledge_os/metadata.py` -> `services/knowledge-engine/src/cial_knowledge_os/metadata.py`
- `src/cial_knowledge_os/phase2_pipeline.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase2_pipeline.py`
- `src/cial_knowledge_os/phase3_pipeline.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase3_pipeline.py`
- `src/cial_knowledge_os/phase3_reporting.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase3_reporting.py`
- `src/cial_knowledge_os/phase3_runner.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase3_runner.py`
- `src/cial_knowledge_os/phase4_checkpoint.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase4_checkpoint.py`
- `src/cial_knowledge_os/phase4_pipeline.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase4_pipeline.py`
- `src/cial_knowledge_os/phase4_reporting.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase4_reporting.py`
- `src/cial_knowledge_os/phase4_runner.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase4_runner.py`
- `src/cial_knowledge_os/phase4_trace.py` -> `services/knowledge-engine/src/cial_knowledge_os/phase4_trace.py`
- `src/cial_knowledge_os/query_transformations.py` -> `services/knowledge-engine/src/cial_knowledge_os/query_transformations.py`
- `src/cial_knowledge_os/rag_pipeline.py` -> `services/knowledge-engine/src/cial_knowledge_os/rag_pipeline.py`
- `src/cial_knowledge_os/reranker.py` -> `services/knowledge-engine/src/cial_knowledge_os/reranker.py`
- `src/cial_knowledge_os/retrieval.py` -> `services/knowledge-engine/src/cial_knowledge_os/retrieval.py`
- `src/cial_knowledge_os/retrieval_postprocessing.py` -> `services/knowledge-engine/src/cial_knowledge_os/retrieval_postprocessing.py`
- `src/cial_knowledge_os/retrieval_trace.py` -> `services/knowledge-engine/src/cial_knowledge_os/retrieval_trace.py`
- `src/cial_knowledge_os/retrievers.py` -> `services/knowledge-engine/src/cial_knowledge_os/retrievers.py`
- `src/cial_knowledge_os/run_manager.py` -> `services/knowledge-engine/src/cial_knowledge_os/run_manager.py`
- `src/cial_knowledge_os/token_budget.py` -> `services/knowledge-engine/src/cial_knowledge_os/token_budget.py`
- `src/cial_knowledge_os/vectorstore.py` -> `services/knowledge-engine/src/cial_knowledge_os/vectorstore.py`

### Place OCR files in `services/knowledge-engine/src/cial_knowledge_os/ocr/`

- `src/cial_knowledge_os/ocr/__init__.py` -> `services/knowledge-engine/src/cial_knowledge_os/ocr/__init__.py`
- `src/cial_knowledge_os/ocr/base_ocr.py` -> `services/knowledge-engine/src/cial_knowledge_os/ocr/base_ocr.py`
- `src/cial_knowledge_os/ocr/ocr_factory.py` -> `services/knowledge-engine/src/cial_knowledge_os/ocr/ocr_factory.py`
- `src/cial_knowledge_os/ocr/tesseract_ocr.py` -> `services/knowledge-engine/src/cial_knowledge_os/ocr/tesseract_ocr.py`

### Place execution and observability files in `services/knowledge-engine/src/cial_knowledge_os/execution/`

- `src/cial_knowledge_os/execution/__init__.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/__init__.py`
- `src/cial_knowledge_os/execution/console.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/console.py`
- `src/cial_knowledge_os/execution/events.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/events.py`
- `src/cial_knowledge_os/execution/event_bus.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/event_bus.py`
- `src/cial_knowledge_os/execution/json_trace.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/json_trace.py`
- `src/cial_knowledge_os/execution/manager.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/manager.py`
- `src/cial_knowledge_os/execution/metrics.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/metrics.py`
- `src/cial_knowledge_os/execution/progress.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/progress.py`
- `src/cial_knowledge_os/execution/renderers.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/renderers.py`
- `src/cial_knowledge_os/execution/schemas.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/schemas.py`
- `src/cial_knowledge_os/execution/telemetry.py` -> `services/knowledge-engine/src/cial_knowledge_os/execution/telemetry.py`

### Place infrastructure helpers in `services/knowledge-engine/src/cial_knowledge_os/infra/`

- `src/cial_knowledge_os/infra/__init__.py` -> `services/knowledge-engine/src/cial_knowledge_os/infra/__init__.py`
- `src/cial_knowledge_os/infra/preflight.py` -> `services/knowledge-engine/src/cial_knowledge_os/infra/preflight.py`
- `src/cial_knowledge_os/infra/qdrant_health.py` -> `services/knowledge-engine/src/cial_knowledge_os/infra/qdrant_health.py`
- `src/cial_knowledge_os/infra/system_health.py` -> `services/knowledge-engine/src/cial_knowledge_os/infra/system_health.py`

### Place tokenizer asset files in `services/knowledge-engine/src/cial_knowledge_os/assets/`

- `src/cial_knowledge_os/assets/9b5ad71b2ce5302211f9c61530b329a4922fc6a4` -> `services/knowledge-engine/src/cial_knowledge_os/assets/9b5ad71b2ce5302211f9c61530b329a4922fc6a4`
- `src/cial_knowledge_os/assets/README.md` -> `services/knowledge-engine/src/cial_knowledge_os/assets/README.md`

### Place scripts in `services/knowledge-engine/scripts/`

- `scripts/run_phase4_batch.py` -> `services/knowledge-engine/scripts/run_phase4_batch.py`
- `scripts/run_phase4_interactive.py` -> `services/knowledge-engine/scripts/run_phase4_interactive.py`
- `scripts/check_qdrant_health.py` -> `services/knowledge-engine/scripts/check_qdrant_health.py`
- `scripts/migrate_embedded_qdrant_to_server.py` -> `services/knowledge-engine/scripts/migrate_embedded_qdrant_to_server.py`
- `scripts/start_qdrant.bat` -> `services/knowledge-engine/scripts/start_qdrant.bat`
- `scripts/stop_qdrant.bat` -> `services/knowledge-engine/scripts/stop_qdrant.bat`

### Place backend docs in `services/knowledge-engine/docs/backend/`

- `docs/CURRENT_STATE.md` -> `services/knowledge-engine/docs/backend/CURRENT_STATE.md`
- `docs/PROJECT_REQUIREMENTS.md` -> `services/knowledge-engine/docs/backend/PROJECT_REQUIREMENTS.md`
- `docs/qdrant_backend.md` -> `services/knowledge-engine/docs/backend/qdrant_backend.md`
- `docs/execution_observability.md` -> `services/knowledge-engine/docs/backend/execution_observability.md`
- `docs/AUTOMATED_EVALUATION.md` -> `services/knowledge-engine/docs/backend/AUTOMATED_EVALUATION.md`
- `docs/BATCH_QA_EXPORT.md` -> `services/knowledge-engine/docs/backend/BATCH_QA_EXPORT.md`
- `docs/PROJECT_RULES.md` -> `services/knowledge-engine/docs/backend/PROJECT_RULES.md`
- `docs/NOTEBOOK_GUIDELINES.md` -> `services/knowledge-engine/docs/backend/NOTEBOOK_GUIDELINES.md`
- `docs/deployment/local_docker.md` -> `services/knowledge-engine/docs/backend/local_docker.md`
- `docs/deployment/offline_release_plan.md` -> `services/knowledge-engine/docs/backend/offline_release_plan.md`

### Place shared full-stack architecture docs in `docs/architecture/`

If you want some backend docs visible at the integrated-repo root instead of inside the backend service, copy duplicates or move summaries here:

- backend architecture summary derived from `docs/CURRENT_STATE.md` -> `docs/architecture/backend-architecture.md`
- migration summary derived from this manifest -> `docs/architecture/backend-migration.md`

### Place benchmark assets in `data/benchmarks/cisg/`

- `data/benchmarks/cisg/README.md` -> `data/benchmarks/cisg/README.md`
- `data/benchmarks/cisg/CHANGELOG.md` -> `data/benchmarks/cisg/CHANGELOG.md`
- `data/benchmarks/cisg/benchmark_answers.csv` -> `data/benchmarks/cisg/benchmark_answers.csv`
- `data/benchmarks/cisg/benchmark_metadata.json` -> `data/benchmarks/cisg/benchmark_metadata.json`
- `data/benchmarks/cisg/cisg_questions_v1.txt` -> `data/benchmarks/cisg/cisg_questions_v1.txt`

### Place manual QA assets in `data/manual_qa/`

- `data/manual_qa/airport_operations_questions.txt` -> `data/manual_qa/airport_operations_questions.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_10_Questions.txt` -> `data/manual_qa/CIAL_Enterprise_Long_Horizon_10_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Long_Horizon_200_Questions.txt` -> `data/manual_qa/CIAL_Enterprise_Long_Horizon_200_Questions.txt`
- `data/manual_qa/CIAL_Enterprise_Stress_Test_500_Questions.txt` -> `data/manual_qa/CIAL_Enterprise_Stress_Test_500_Questions.txt`
- `data/manual_qa/CIAL_Multimodal_Test_Questions.txt` -> `data/manual_qa/CIAL_Multimodal_Test_Questions.txt`
- `data/manual_qa/cybersecurity_questions.txt` -> `data/manual_qa/cybersecurity_questions.txt`
- `data/manual_qa/easa_qns.txt` -> `data/manual_qa/easa_qns.txt`
- `data/manual_qa/phase4_hal.txt` -> `data/manual_qa/phase4_hal.txt`
- `data/manual_qa/phase4_questions.txt` -> `data/manual_qa/phase4_questions.txt`
- `data/manual_qa/phase4_questions_small.txt` -> `data/manual_qa/phase4_questions_small.txt`
- `data/manual_qa/smoke_questions.txt` -> `data/manual_qa/smoke_questions.txt`

### Place optional deterministic regression corpus in `data/test_corpus/`

- `data/files/Test/` -> `data/test_corpus/`

If you want the test corpus to behave exactly like the current repo's canonical corpus contract, place it instead at:

- `data/files/Test/` -> `data/files/Test/`

Use only one of those options.

### Place optional reference notebooks

If you want to retain engineering notebooks inside the backend service:

- `notebooks/01_Basic_RAG.ipynb` -> `services/knowledge-engine/docs/backend/notebooks/01_Basic_RAG.ipynb`
- `notebooks/02_Query_Transformations_and_Context_Construction.ipynb` -> `services/knowledge-engine/docs/backend/notebooks/02_Query_Transformations_and_Context_Construction.ipynb`
- `notebooks/03_Hybrid_Retrieval.ipynb` -> `services/knowledge-engine/docs/backend/notebooks/03_Hybrid_Retrieval.ipynb`
- `notebooks/04_Reranking_and_Evidence_Selection.ipynb` -> `services/knowledge-engine/docs/backend/notebooks/04_Reranking_and_Evidence_Selection.ipynb`
- `notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb` -> `services/knowledge-engine/docs/backend/notebooks/045_Multimodal_Test_Corpus_Evaluation.ipynb`

### Place optional tests in `services/knowledge-engine/tests/`

- `tests/test_batch_qa.py` -> `services/knowledge-engine/tests/test_batch_qa.py`
- `tests/test_corpus_architecture.py` -> `services/knowledge-engine/tests/test_corpus_architecture.py`
- `tests/test_evaluation_framework.py` -> `services/knowledge-engine/tests/test_evaluation_framework.py`
- `tests/test_execution_observability.py` -> `services/knowledge-engine/tests/test_execution_observability.py`
- `tests/test_file_formats.py` -> `services/knowledge-engine/tests/test_file_formats.py`
- `tests/test_incremental_index.py` -> `services/knowledge-engine/tests/test_incremental_index.py`
- `tests/test_infrastructure_hardening.py` -> `services/knowledge-engine/tests/test_infrastructure_hardening.py`
- `tests/test_ocr_imports.py` -> `services/knowledge-engine/tests/test_ocr_imports.py`
- `tests/test_phase2.py` -> `services/knowledge-engine/tests/test_phase2.py`
- `tests/test_phase2_regressions.py` -> `services/knowledge-engine/tests/test_phase2_regressions.py`
- `tests/test_phase2_visualization.py` -> `services/knowledge-engine/tests/test_phase2_visualization.py`
- `tests/test_phase3_artifacts.py` -> `services/knowledge-engine/tests/test_phase3_artifacts.py`
- `tests/test_phase3_retrieval.py` -> `services/knowledge-engine/tests/test_phase3_retrieval.py`
- `tests/test_phase4.py` -> `services/knowledge-engine/tests/test_phase4.py`
- `tests/test_phase4_cli.py` -> `services/knowledge-engine/tests/test_phase4_cli.py`
- `tests/test_phase4_reporting.py` -> `services/knowledge-engine/tests/test_phase4_reporting.py`
- `tests/test_phase4_runner_limits.py` -> `services/knowledge-engine/tests/test_phase4_runner_limits.py`
- `tests/test_qdrant_backends.py` -> `services/knowledge-engine/tests/test_qdrant_backends.py`
- `tests/test_sample_documents.py` -> `services/knowledge-engine/tests/test_sample_documents.py`

### Do not copy these as source files

Leave these as generated runtime folders in the new repo and keep them gitignored:

- `data/indexes/`
- `data/bm25/`
- `data/qdrant/`
- `data/qdrant_server/`
- `data/outputs/`

Do not copy the current contents from the old repo into those folders.

## Continuous Indexer Runtime Inventory

Runtime-critical additions:

- `backend/indexer_main.py`
- `backend/app/services/continuous_indexer.py`
- `backend/app/services/indexing_queue.py`
- `src/cial_knowledge_os/bm25_snapshot.py`
- `alembic/versions/20260724_0016_continuous_indexing.py`
- `scripts/start_indexer.bat`
- `scripts/start_indexer.ps1`
- `docs/architecture/CONTINUOUS_INDEXING_ARCHITECTURE.md`

The API and indexer must migrate together with Qdrant server configuration.
Do not migrate a backend composition root that starts `IndexingWorker` or
`CorpusWatcher` in FastAPI. Do not copy BM25 runtime snapshots as source; they
are regenerated and atomically published under the configured app-data root.
