# Corpus Synchronization Engine

Status: implemented as `cial_knowledge_os.corpus`.

```text
Filesystem
    |
    v
Recursive Scanner
    |
    v
Corpus Tree Builder
    |
    v
Metadata Diff Engine
    |
    v
PostgreSQL Metadata Update
    |
    v
Incremental Index Job Queue
    |
    v
Qdrant
```

The synchronizer makes PostgreSQL the authoritative metadata layer while the
filesystem remains the authoritative document store and Qdrant remains the
authoritative vector store.

## Workflow

1. Recursively scan `data/files`.
2. Compute deterministic file hashes with `CIAL_CORPUS_HASH` (`sha256` by
   default).
3. Build a Corpus Tree with folder hierarchy and parent-child relationships.
4. Compare the tree against PostgreSQL metadata.
5. Update `folders`, `documents`, and `document_versions` transactionally.
6. Record `ingestion_runs`.
7. Queue `indexing_jobs` for added or content-modified documents.

Moves, renames, and deletes are metadata updates only. Deleted files are marked
`deleted`; they are not hard-deleted and do not trigger vector rebuilds in this
phase. The sync engine never performs retrieval, prompt rendering, generation,
citation construction, or vector writes.

## Startup Behavior

`CIAL_CORPUS_SYNC_ON_STARTUP=true` runs Corpus sync during backend startup
before the existing Phase 4.5 readiness checks. Sync failures are logged and do
not crash the API process.

`CIAL_CORPUS_WATCH=false` by default. When enabled, watchdog observes
filesystem changes, debounces events, runs metadata sync, and queues indexing
jobs without requiring a restart.

## Logging

The synchronizer records:

- folders scanned
- files scanned
- added folders/files
- removed folders/files
- moved folders/files
- renamed files
- modified files
- unchanged files
- queued indexing jobs
- elapsed time

## Performance

Current sync is deterministic and simple:

- Recursive filesystem traversal is ordered by relative path.
- File hashes are streamed in 1 MiB chunks.
- Metadata updates run in one SQL transaction.
- The default metadata batch size setting is `CIAL_METADATA_BATCH_SIZE=500`.
- Unchanged files do not create indexing jobs.

Future large-corpus optimization can add provider cursors, filesystem mtimes as
a pre-hash guard, and chunked DB writes while preserving the same Corpus API.
