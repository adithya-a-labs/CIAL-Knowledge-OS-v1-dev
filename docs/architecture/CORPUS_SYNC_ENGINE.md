# Corpus Synchronization Engine

Status: implemented as the metadata-only `cial_knowledge_os.corpus` service.
See [Continuous Indexing Architecture](CONTINUOUS_INDEXING_ARCHITECTURE.md).

```text
watchdog events + periodic scan
              |
              v
scanner -> tree/diff -> PostgreSQL metadata + ingestion_run
                              |
                              v
                    durable indexing_jobs
                              |
                              v
                  standalone indexer (vectors)
```

The filesystem is the original-document store, PostgreSQL is authoritative for
metadata/work state, and Qdrant is authoritative for verified vectors. The
Corpus Synchronization Engine never extracts, embeds, or writes vectors.

## Workflow

1. Resolve and contain the configured enabled repository root.
2. Ignore unsupported types, Office locks, partial uploads, hidden/system
   artifacts, application caches, outputs, and vector storage.
3. Compare deterministic filesystem state with PostgreSQL.
4. Use size/mtime as the cheap guard and SHA-256 for content confirmation.
5. Update folders, documents, immutable versions, and `ingestion_runs` in a
   transaction.
6. Queue `upsert_version`, `delete_asset`, or `refresh_metadata`.
7. Preserve identity for a same-hash/size move or rename.

## Watcher

The standalone indexer owns watchdog observers for the configured enterprise
repository and `CIAL_WORKSPACE_ROOT`. Create, modify, delete, move, rename, and
directory events are coalesced per debounce window. A file must have stable
size/mtime over the configured checks and open successfully before the sync
runs. Watcher loss is covered by periodic reconciliation.

## Reconciliation

One reconciliation runs when the indexer starts and repeats every 300 seconds
by default. A PostgreSQL advisory lock prevents overlapping complete scans.
Unchanged assets create no jobs. Indexer startup against an unchanged,
complete repository performs no extraction or embedding.

`POST /api/corpus/sync` enqueues a reconciliation request and returns `202`;
the API process does not scan or index synchronously.

## Configuration and Logging

Watcher/reconciliation settings are documented in
`CONTINUOUS_INDEXING_ARCHITECTURE.md`. Structured summaries report scanned,
added, modified, moved, renamed, removed, unchanged, jobs queued, stability
timeouts, and elapsed time without logging private absolute paths.
