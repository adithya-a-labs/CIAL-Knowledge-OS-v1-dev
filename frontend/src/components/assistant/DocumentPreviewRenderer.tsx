import { Suspense, lazy } from 'react';
import { apiUrl } from '@/api/client';
import type { DocumentPreview } from '@/api/types';
import FallbackViewer from './renderers/FallbackViewer';
import HtmlViewer from './renderers/HtmlViewer';
import ImageViewer from './renderers/ImageViewer';
import PptxViewer from './renderers/PptxViewer';
import SpreadsheetViewer from './renderers/SpreadsheetViewer';
import TextViewer from './renderers/TextViewer';

const PdfViewer = lazy(() => import('./renderers/PdfViewer'));

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
}: {
  preview: DocumentPreview | null;
  title: string;
  searchQuery: string;
  zoomLevel: number;
  activePage: number;
  requestedPage: number;
  onPageCountChange: (value: number) => void;
  onActivePageChange: (value: number) => void;
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

  if (preview.render_kind === 'pdf' && viewerUrl) {
    return (
      <Suspense fallback={<div className="rounded-2xl border border-border bg-white p-4 text-sm text-muted-foreground">Loading document viewer...</div>}>
        <PdfViewer
          fileUrl={viewerUrl}
          title={title}
          activePage={activePage}
          requestedPage={requestedPage}
          searchQuery={searchQuery}
          highlightText={preview.highlight_text || ''}
          zoomLevel={zoomLevel}
          onPageCountChange={onPageCountChange}
          onVisiblePageChange={onActivePageChange}
        />
      </Suspense>
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
