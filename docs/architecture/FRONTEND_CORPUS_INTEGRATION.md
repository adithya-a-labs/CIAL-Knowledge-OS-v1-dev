# Frontend Corpus Integration

Status: implemented for Knowledge Center and Assistant integration.

## Flow

```text
Knowledge Center
  -> Corpus API
  -> PostgreSQL metadata
  -> Filesystem only through backend sync

Assistant Context Picker
  -> Corpus Tree
  -> selected document/folder context
  -> POST /api/chat

Citations / Sources
  -> source resolver
  -> Corpus document preview
  -> right-side document viewer
```

## API Usage

- `GET /api/corpus/tree` renders the Knowledge Center tree and context picker.
- `GET /api/corpus/folder?path=<relative_path>` renders folder contents with folders first, then files.
- `GET /api/corpus/document/{id}` reads document metadata.
- `GET /api/corpus/document/{id}/preview?chunk_id=&page=` feeds the source viewer.
- `POST /api/corpus/sync` manually refreshes Corpus metadata.
- `POST /api/chat` receives selected document ids, selected folder ids, response length, and response profile.

## Response Modes

- Quick -> `response_length: "short"`, `profile: "quick"`
- Standard -> `response_length: "medium"`, `profile: "standard"`
- Detailed -> `response_length: "long"`, `profile: "detailed"`
- Operational -> `response_length: "long"`, `profile: "operational"`

## Known Limitations

- Full binary file streaming is not exposed yet, so PDF, image, DOCX, XLSX, and PPTX previews show metadata and cited excerpts until a document-serving endpoint is added.
- Folder context is expanded to document ids on the frontend while also passing folder ids for future backend support.
- If the backend is unavailable, Knowledge Center and context picker show labeled demo data only.

## My Workspace Integration

My Workspace consumes `/api/workspaces/me/tree`, `/root`, `/folders/{id}`, `/summary`, and `/preferences`. It uses the shared `/knowledge/document/{id}` viewer route and Corpus preview/file endpoints rather than introducing a second viewer. If workspace APIs are unavailable, its static preview is explicitly labelled and preference persistence is clearly labelled browser-local.

## Background Indexing States

The frontend reads `api_ready`, `retrieval_ready`, `indexer_seen`,
`indexer_state`, and `queue_counts`. Chat is gated by `retrieval_ready`, not by
an empty queue. When a committed generation exists, active indexing produces a
non-blocking banner and chat remains usable. Upload rows appear immediately,
poll document status, and present Queued, Extracting, Preparing, Embedding,
Indexing, Ready, Failed, or Unavailable labels. Note database save state is not
conflated with its separate AI-index state.
