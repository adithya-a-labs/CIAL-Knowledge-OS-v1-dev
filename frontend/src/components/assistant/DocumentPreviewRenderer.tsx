import { apiUrl } from '@/api/client';
import type { DocumentPreview } from '@/api/types';
import FallbackViewer from './renderers/FallbackViewer';
import HtmlViewer from './renderers/HtmlViewer';
import ImageViewer from './renderers/ImageViewer';
import PptxViewer from './renderers/PptxViewer';
import SpreadsheetViewer from './renderers/SpreadsheetViewer';
import TextViewer from './renderers/TextViewer';

function extensionOf(preview: DocumentPreview | null, fallbackTitle: string) {
  return (preview?.extension || fallbackTitle.split('.').pop() || '').replace(/^\./, '').toLowerCase();
}

export default function DocumentPreviewRenderer({
  preview,
  title,
  searchQuery,
  zoomLevel,
  activePage,
  requestedPage,
  onPageCountChange,
  onActivePageChange,
  useNativePdf = false,
}: {
  preview: DocumentPreview | null;
  title: string;
  searchQuery: string;
  zoomLevel: number;
  activePage: number;
  requestedPage: number;
  onPageCountChange: (value: number) => void;
  onActivePageChange: (value: number) => void;
  useNativePdf?: boolean;
}) {
  const extension = extensionOf(preview, title);
  const text = preview?.preview_text ?? '';
  const viewerUrl = preview?.viewer_url ? apiUrl(preview.viewer_url) : preview?.file_url ? apiUrl(preview.file_url) : null;
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension);

  if (!preview) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-[hsl(210_20%_98%)] p-5 text-center text-sm text-muted-foreground">
        Select a citation to open the document viewer.
      </div>
    );
  }

  if (preview.render_kind === 'pdf' && viewerUrl && useNativePdf) {
    return (
      <div className="flex h-full min-h-[28rem] flex-col overflow-hidden rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)]">
        <iframe
          src={`${viewerUrl}#page=${requestedPage || activePage || 1}&zoom=${Math.round(zoomLevel * 100)}`}
          title={title}
          className="min-h-0 flex-1 bg-white"
          onLoad={() => {
            if (preview.page_count) onPageCountChange(preview.page_count);
            onActivePageChange(requestedPage || activePage || 1);
          }}
        />
        <div className="border-t border-border bg-white px-4 py-2 text-xs text-muted-foreground">
          If the browser cannot display this PDF inline, use Open or Download from the document toolbar.
        </div>
      </div>
    );
  }

  if (preview.render_kind === 'pdf') {
    return (
      <div className="flex h-full min-h-[24rem] items-center justify-center rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-6 text-center">
        <div className="max-w-md">
          <p className="text-sm font-semibold text-foreground">PDF preview available</p>
          <p className="mt-2 text-xs leading-5 text-muted-foreground">
            Open the source in the full Document Workspace or use the toolbar actions to inspect the original PDF. The cited excerpt and metadata remain available below.
          </p>
        </div>
      </div>
    );
  }

  if (isImage && viewerUrl) {
    return <ImageViewer src={viewerUrl} title={title} zoomLevel={zoomLevel} />;
  }

  if (preview.render_kind === 'spreadsheet' || preview.render_kind === 'table') {
    return (
      <SpreadsheetViewer
        rows={preview.table_rows ?? []}
        sheetNames={preview.sheet_names}
        activeSheet={preview.active_sheet}
        searchQuery={searchQuery}
        zoomLevel={zoomLevel}
      />
    );
  }

  if (preview.render_kind === 'slides' && preview.slides?.length) {
    return (
      <PptxViewer
        slides={preview.slides}
        activePage={activePage}
        searchQuery={searchQuery}
        zoomLevel={zoomLevel}
        onSelectPage={onActivePageChange}
      />
    );
  }

  if ((preview.render_kind === 'docx' || preview.render_kind === 'markdown' || preview.render_kind === 'html') && preview.rendered_html) {
    return <HtmlViewer html={preview.rendered_html} zoomLevel={zoomLevel} />;
  }

  if (preview.render_kind === 'text' || preview.render_kind === 'code') {
    return <TextViewer text={text} searchQuery={searchQuery} zoomLevel={zoomLevel} code={preview.render_kind === 'code'} />;
  }

  if (preview.preview_text) {
    return <TextViewer text={text} searchQuery={searchQuery} zoomLevel={zoomLevel} />;
  }

  return <FallbackViewer extension={extension} isImage={isImage} notice={preview.preview_notice} />;
}
