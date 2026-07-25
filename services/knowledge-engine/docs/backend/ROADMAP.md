# CIAL Knowledge OS Roadmap

## Implemented

- Standalone always-running continuous indexer
- PostgreSQL durable queue, leases, recovery, heartbeats, and generations
- Enterprise/personal filesystem watching plus periodic reconciliation
- Enterprise, personal, chat-attachment, and note indexing triggers
- Rapid note revision supersession
- Bounded CPU extraction and cross-document embedding batches
- Separate normal and OCR extraction pools with normal-work priority
- Adaptive 64/128/256 GPU batching with CUDA-OOM reduction and CPU-safe
  precision fallback
- CPU/GPU utilization plus documents/hour and chunks/minute worker telemetry
- Verified version replacement, delete, and metadata-refresh operations
- Dedicated bounded Qdrant writer stage that drains independently of GPU work
- Atomic BM25 publication and FastAPI hot reload
- Independent backend/indexer Windows launch and installer wiring

## Deferred

- Coordinated multi-GPU scheduling and dynamic GPU assignment across several
  indexer processes
- Non-filesystem enterprise providers beyond the existing storage abstraction
- Organization-default workspace preference administration
- Sharing/transfer/revocation APIs for personal knowledge

Deferred items do not change the current Phase 4.5 prompt or introduce Phase 5
agentic behavior.
