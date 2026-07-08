# Data Directory Policy

This directory is reserved for local corpus inputs, benchmark fixtures, and runtime state.

- `Test/` may contain committed sample or benchmark material used for migration validation.
- `files/`, `pdf/`, and `documents/` are local corpus mount points and should not be committed.
- `qdrant/`, `qdrant_server/`, `bm25/`, `indexes/`, `outputs/`, and cache folders are generated runtime state and should not be committed.
- `indexes/document_manifest.json` is regenerated from the active local corpus and should stay uncommitted.
