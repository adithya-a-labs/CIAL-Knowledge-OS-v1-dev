# Document Preview System

The document preview system exposes corpus files through metadata-backed API routes. Frontend code never receives a filesystem path; it uses document ids returned by the Corpus API.

## Endpoints

- `GET /api/corpus/document/{id}/file`
  - Resolves `{id}` through PostgreSQL corpus metadata.
  - Resolves `relative_path` under `data/files`.
  - Rejects absolute paths, `..` traversal, and files outside the corpus root.
  - Streams the file with `FileResponse`.

- `GET /api/corpus/document/{id}/thumbnail?page=`
  - Uses the same safe document resolution.
  - Caches generated thumbnails under `outputs/thumbnails`.
  - Cache names include document id, content hash, and page, so unchanged files reuse existing thumbnails and changed files regenerate.
  - PDF thumbnails use PyMuPDF when available. Images use Pillow resizing. CSV/XLSX and other formats use a generated PNG card or table snapshot. OCR is not used.

- `GET /api/corpus/document/{id}/preview?page=&chunk_id=`
  - Returns document metadata plus preview fields:
    - `file_url`, `thumbnail_url`, `preview_text`, `table_rows`
    - `render_kind`, `extraction_method`
    - `page`, `chunk_id`, `highlight_text`
  - Text-like files are read with a byte cap, so large files are not fully loaded.
  - Office formats return an extracted DOCX preview when available, otherwise a polished metadata card.

## Format Behavior

- PDF: streamed file preview with page-aware thumbnail.
- PNG, JPG, JPEG, TIFF, BMP, WEBP, GIF: streamed image preview and resized thumbnail.
- TXT, MD, HTML, JSON, XML, YAML: safe text/code preview with capped reads.
- CSV: capped table preview and table thumbnail.
- XLSX/XLS: read-only first-sheet snapshot when `openpyxl` can read it; otherwise metadata card.
- DOCX: paragraph preview when `python-docx` can extract text.
- DOC, PPTX, PPT: metadata/type card until a full renderer is introduced.
- Unknown formats: metadata/type card with safe file streaming.

## Frontend Use

`CorpusExplorer` is the shared browser for Knowledge Center and Manage Context. It consumes only Corpus API data, renders lazy thumbnails, supports tree navigation, breadcrumbs-by-folder context, search, sort, grid/list views, and a right-side source viewer.

Manage Context uses `CorpusExplorer mode="select"` so folder/file navigation and preview behavior match Knowledge Center. Selection state stays in the assistant panel and is persisted in local storage only after Apply. Chat requests include selected document ids, selected folder ids, response length, and profile. Folder selections are expanded to document ids in the frontend for the current backend chat path while still sending folder ids for future backend support.
