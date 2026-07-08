# Corpus Architecture

Status: backend foundation implemented.

The Corpus layer is the backend abstraction for the enterprise knowledge
repository. User-facing product language can remain Knowledge Center, but
backend systems should use Corpus, Corpus Tree, Corpus Explorer, Corpus
Synchronization Engine, and Corpus API.

## Philosophy

The frontend should never know where documents are stored. It should consume
Corpus APIs backed by PostgreSQL metadata. Storage discovery is a backend
responsibility.

```text
Storage Provider
        |
        v
Corpus Scanner
        |
        v
Corpus Tree
        |
        v
Corpus Synchronization Engine
        |
        v
PostgreSQL Metadata
        |
        +--------> Knowledge Center
        +--------> AI Assistant
        +--------> Document Picker
        +--------> Search
        +--------> Future Features

                    |
                    v
           Incremental Index Queue
                    |
                    v
                 Qdrant
```

## Object Model

`CorpusTree` is the canonical in-memory representation of the repository:

- `CorpusFolder`: `id`, `parent_id`, `name`, `relative_path`, `depth`,
  `document_count`, `subfolder_count`, `last_scanned_at`
- `CorpusFile`: `id`, `folder_id`, `name`, `relative_path`, `extension`,
  `mime_type`, `size_bytes`, `content_hash`, `modified_at`, `indexed`,
  `indexing_status`, `page_count`

The implemented Python package is `cial_knowledge_os.corpus`. A compatibility
package exists at `cial_knowledge_os.corpus_sync`, but new code should use
`cial_knowledge_os.corpus`.

## Storage Abstraction

Today the storage provider is the local filesystem under `data/files`.

Future providers can feed the same scanner/tree contract without frontend
changes:

- Local filesystem
- Network share / SMB
- SharePoint
- OneDrive
- Google Drive
- S3-compatible storage
- Azure Blob Storage

## Metadata Lifecycle

1. Scanner recursively discovers the storage provider.
2. Tree builder creates a hierarchical Corpus Tree.
3. Synchronizer compares the tree with PostgreSQL metadata.
4. Metadata updates are written transactionally.
5. Affected documents are marked `pending` or `deleted`.
6. Pending indexing jobs are queued for later vector/index work.
7. Qdrant remains the vector store; the sync engine does not write vectors.

Indexing states:

- `pending`
- `indexing`
- `indexed`
- `failed`
- `deleted`

Move and rename detection is based on deterministic content hash plus file
size. This preserves the document row when the same file appears at a new
relative path. Folder move detection uses subtree content signatures where
available.

## PostgreSQL Tables

The Corpus layer uses:

- `folders`
- `documents`
- `document_versions`
- `ingestion_runs`
- `indexing_jobs`

It does not store source file contents or embeddings.

## API Contracts

`GET /api/corpus/tree`

Returns the hierarchical Corpus Tree from PostgreSQL metadata.

`GET /api/corpus/folder?path=<relative>`

Returns one folder, immediate child folders, and immediate documents.

`GET /api/corpus/document/{id}`

Returns document metadata by PostgreSQL document id.

`POST /api/corpus/sync`

Runs a manual Corpus synchronization and returns the sync summary.

## Architectural Pillars

The Corpus layer is a core CIAL Knowledge OS pillar alongside:

- Metadata Database: PostgreSQL
- Knowledge Engine: Phase 4.5
- Vector Store: Qdrant
- Frontend: Knowledge Center and related UI surfaces
