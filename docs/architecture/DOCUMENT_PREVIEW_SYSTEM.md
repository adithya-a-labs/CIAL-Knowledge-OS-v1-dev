# Document Preview System

The document preview system is the shared viewer stack for Knowledge Center, citation review in Chat, and any future search-result or context-management preview surface. Frontend code never receives filesystem paths. All viewer and thumbnail state is anchored on corpus metadata and document ids.

## Viewer

- `SourceViewerPanel` is the responsive shell used across assistant and corpus browsing.
- `DocumentViewerPanel` is the single reusable document surface.
- Viewer state is explicit:
  - `activeDocument`
  - `activePage`
  - `activeChunk`
- Citation jumps open the same viewer path used by Knowledge Center cards, so deep links and preview behavior are consistent.
- Layout priority is viewer-first:
  - filename
  - toolbar
  - dominant preview area
  - excerpt
  - metadata

## Deep Links

- Chat source payloads now carry stable preview metadata:
  - `document_id`
  - `relative_path`
  - `page`
  - `page_count`
  - `chunk_id`
  - `highlight_text`
  - `preview_text`
  - `file_type`
  - `file_url`
- `GET /api/corpus/document/{id}/preview?page=&chunk_id=` resolves:
  - document metadata
  - page-aware preview state
  - chunk-aware highlight state
- Missing `document_id` values are resolved on the backend from corpus metadata before the frontend opens a viewer.
- Absolute filesystem paths are not returned to the frontend.

## Preview Pipeline

1. Frontend requests `/api/corpus/document/{id}/preview?page=&chunk_id=`.
2. Backend validates `relative_path` under `data/files`.
3. Preview cache key is built from:
   - document id
   - content hash
   - page
   - chunk id
4. Backend returns a format-specific payload:
   - `preview_text`
   - `highlight_text`
   - `render_kind`
   - `rendered_html`
   - `table_rows`
   - `sheet_names`
   - `slides`
   - `page_count`
   - action URLs

The preview pipeline is intentionally capped. Large files are sampled, first-page/first-sheet/first-slide extraction is preferred, and full-file reads are avoided.

## Thumbnail Pipeline

- `GET /api/corpus/document/{id}/thumbnail?page=` reuses the same safe resolution path.
- Cache is stored under `outputs/thumbnails`.
- Cache keys are content-hash aware, so unchanged files reuse thumbnails and modified files regenerate automatically.
- Native thumbnail strategy:
  - PDF: first requested page via PyMuPDF
  - Images: resized source image via Pillow
  - CSV/XLS/XLSX: first visible rows
  - DOCX/PPTX/MD/HTML/JSON/TXT and similar formats: content-aware card generated from preview text
  - Fallback: file card
- OCR is not used for thumbnail generation.

## Cache

- Preview cache: `outputs/previews`
- Thumbnail cache: `outputs/thumbnails`
- Both caches are keyed by document id plus content hash, so corpus sync or re-index updates invalidate naturally when content changes.
- Frontend reuses:
  - preview responses through React Query
  - thumbnail URLs through browser caching

## Supported Formats

- PDF: inline file viewer with page-aware deep links and extracted page text.
- DOCX: rendered prose/table preview.
- DOC: metadata-card fallback unless richer extraction is added.
- PPTX: slide-strip plus active-slide viewer.
- PPT: metadata-card fallback unless richer extraction is added.
- XLSX/XLS: first-sheet spreadsheet preview with sheet metadata.
- CSV: table preview.
- TXT: typography/text preview.
- MD: rendered markdown preview.
- HTML: sanitized HTML preview.
- JSON/XML/YAML: formatted code preview.
- PNG/JPG/JPEG/WEBP/BMP/GIF/TIFF: zoomable image preview.

## Performance

- Lazy thumbnail loading remains the default list/grid behavior.
- Preview payloads stream only the data needed for the active format.
- No OCR work is performed for thumbnails.
- No full-file load is required for standard preview paths.
- Spreadsheet, text, and slide previews are capped to keep viewer latency bounded.

## Extensibility

- Add new formats in `backend/app/services/document_preview_service.py`.
- New formats should provide:
  - `render_kind`
  - bounded preview extraction
  - content-aware thumbnail fallback
  - safe action URLs
- Frontend viewer support should be added only in `DocumentPreviewRenderer` so Knowledge Center, Chat citations, and future result panels stay on the same rendering path.
