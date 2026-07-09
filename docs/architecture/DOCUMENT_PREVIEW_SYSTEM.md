# Document Preview System

The document preview system is the shared rendering stack for Knowledge Center, Chat citations, Manage Context preview, and future search-driven document surfaces. Frontend code never receives filesystem paths. Every viewer state transition is anchored on corpus document ids and corpus-relative metadata.

## Viewer Architecture

- `SourceViewerPanel` is the responsive shell.
- `DocumentViewerPanel` is the single reusable document surface.
- `DocumentPreviewRenderer` dispatches to format-specific viewer components.
- Current renderer set:
  - `PdfViewer`
  - `HtmlViewer`
  - `PptxViewer`
  - `SpreadsheetViewer`
  - `TextViewer`
  - `ImageViewer`
  - `FallbackViewer`

Viewer state is explicit and reused across surfaces:

- `activeDocument`
- `activePage`
- `activeChunk`
- `previewPage`

The panel is viewer-first. The preview dominates the surface, the toolbar stays visible, and metadata is secondary/collapsed.

## Backend Rendering Services

Rendering and file-serving logic stays in backend services, not route files.

- `backend/app/services/document_preview_service.py`
  - safe document resolution
  - file serving helpers
  - preview extraction
  - thumbnail generation
  - preview payload shaping
- `backend/app/services/document_rendering_service.py`
  - optional legacy Office conversion
  - rendered-file cache management
  - viewer asset resolution

Routes only resolve corpus metadata and hand off to service functions.

## Endpoints

- `GET /api/corpus/document/{id}/file`
  - streams the original file
  - used by PDF.js and native open/download flows
- `GET /api/corpus/document/{id}/view`
  - inline original-file route retained for backward compatibility
- `GET /api/corpus/document/{id}/download`
  - attachment download route
- `GET /api/corpus/document/{id}/thumbnail?page=`
  - cached thumbnail route
- `GET /api/corpus/document/{id}/preview?page=&chunk_id=`
  - returns preview metadata, viewer metadata, and citation state
- `GET /api/corpus/document/{id}/rendered?format=pdf`
  - serves cached converted assets for supported legacy Office formats

Existing routes remain backward compatible. The new rendered route is additive.

## PDF.js Strategy

PDF now renders in the frontend with `react-pdf` and `pdfjs-dist` instead of relying on the browser inline PDF experience.

Capabilities:

- page-aware load states
- scrollable page stack
- zoom in/out/reset
- current page / total pages
- page jump from toolbar
- citation jump to the cited page
- practical text search/highlight
- citation highlight synchronization with the excerpt panel

The viewer consumes `/api/corpus/document/{id}/file` or a rendered PDF asset when a converted legacy file is being displayed.

## Office Strategy

### DOCX

- Rendered as a document-style article view from sanitized preview HTML.
- Preserves headings, paragraphs, and tables from the preview pipeline.
- Search is intentionally disabled in this pass for rendered HTML surfaces to avoid unsafe DOM mutation of sanitized markup.

### PPTX

- Rendered as a slide-style viewer.
- Left rail shows slide cards.
- Main area shows the selected slide content in a presentation surface.

### XLSX / XLS

- Rendered as a spreadsheet-style grid.
- Sheet tabs are displayed when available.
- First row is styled as a frozen header surrogate.
- Grid scroll is prioritized over metadata.

### Legacy DOC / PPT

- No separate native viewer is built.
- Backend attempts headless LibreOffice conversion to PDF and caches the rendered result under `outputs/rendered/`.
- If conversion is unavailable, the frontend shows a graceful limited-preview surface and keeps original open/download actions available.
- Failure to convert never crashes the viewer path.

## Citation Deep-Link Flow

1. A citation click resolves `document_id`, `page`, and `chunk_id`.
2. The shared viewer opens the matching document.
3. `preview?page=&chunk_id=` returns page-aware highlight data.
4. The frontend jumps the viewer to the target page.
5. The PDF text layer attempts to mark matching excerpt text.
6. If exact text matching is not detected, the viewer keeps the cited page active and the synced excerpt panel explains that the closest available location is shown.
7. Citation `Previous` / `Next` moves the full page/chunk/highlight context, not just the raw source card.

No absolute paths are returned to the browser.

## Preview Pipeline

1. Frontend requests `/api/corpus/document/{id}/preview?page=&chunk_id=`.
2. Backend validates the corpus-relative path under `data/files`.
3. Optional legacy conversion is resolved before format dispatch when applicable.
4. Preview cache key is built from:
   - document id
   - content hash
   - page
   - chunk id
5. Format-specific preview payload is returned with:
   - `preview_text`
   - `highlight_text`
   - `render_kind`
   - `rendered_html`
   - `table_rows`
   - `sheet_names`
   - `active_sheet`
   - `slides`
   - `viewer_url`
   - `viewer_format`
   - `viewer_ready`
   - `preview_notice`

Preview extraction stays bounded. Large files are sampled; first-page/first-sheet/first-slide behavior is preferred over full-document materialization.

## Thumbnail Pipeline

- Cached under `outputs/thumbnails/`
- Keyed by document id + content hash + page
- Strategy:
  - PDF: requested page via PyMuPDF
  - images: resized original
  - CSV/XLSX/XLS: first visible rows
  - DOCX/PPTX/MD/HTML/JSON/TXT and similar formats: content-aware preview card
  - legacy DOC/PPT with successful conversion: PDF-based thumbnail
  - fallback: file card

OCR is never used for thumbnail generation.

## Cache Layout

- `outputs/previews/`
  - preview payload cache
- `outputs/thumbnails/`
  - thumbnail cache
- `outputs/rendered/`
  - converted legacy Office render cache

All caches are content-hash aware so changed files naturally invalidate older preview assets.

## Supported Formats

- PDF: frontend PDF.js viewer
- DOCX: document-style HTML viewer
- DOC: converted PDF if available, otherwise graceful limited-preview fallback
- PPTX: slide-style viewer
- PPT: converted PDF if available, otherwise graceful limited-preview fallback
- XLSX / XLS: spreadsheet-style grid
- CSV: table/grid view
- TXT: text viewer
- MD: rendered markdown
- HTML: sanitized HTML viewer
- JSON / XML / YAML: formatted text/code viewer
- PNG / JPG / JPEG / WEBP / BMP / GIF / TIFF: zoomable image viewer

## Performance Notes

- The PDF renderer is lazy-loaded so the PDF.js bundle is only fetched when a document viewer actually opens a PDF.
- React Query continues to cache preview payloads.
- Thumbnail requests remain lazy at the card level.
- Preview extraction is capped for text, spreadsheet, and slide formats.
- No OCR is performed for thumbnails.
- Files are streamed rather than read wholesale through the API path.

## Limitations

- DOCX rendering is document-like but not a full fidelity Word clone.
- Legacy DOC/PPT rendering depends on local LibreOffice/`soffice` availability.
- PDF text highlighting is best-effort against the PDF text layer; some documents will fall back to cited-page + synced excerpt behavior when exact text spans do not align with extracted chunk text.
- Rendered HTML surfaces currently do not support in-document search highlighting in this pass.

## Extensibility

- Add new backend format dispatch in `document_preview_service.py`.
- Add new conversion strategies in `document_rendering_service.py`.
- Add new frontend renderers behind `DocumentPreviewRenderer` only, so Knowledge Center, Chat, and Manage Context continue to share one document-viewer architecture.
