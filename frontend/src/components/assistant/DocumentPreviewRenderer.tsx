import { useEffect, useMemo, useRef } from 'react';
import { FileArchive, FileImage, FileJson, FileSpreadsheet, FileText, Presentation } from 'lucide-react';
import { apiUrl } from '@/api/client';
import type { DocumentPreview } from '@/api/types';

function extensionOf(preview: DocumentPreview | null, fallbackTitle: string) {
  return (preview?.extension || fallbackTitle.split('.').pop() || '').replace(/^\./, '').toLowerCase();
}

function escapeHtml(value: string) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;');
}

function highlightHtml(value: string, query: string) {
  if (!query.trim()) return escapeHtml(value);
  const pattern = new RegExp(`(${query.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'gi');
  return escapeHtml(value).replace(pattern, '<mark data-search-hit="true" class="rounded bg-[#f9e6a5] px-0.5">$1</mark>');
}

function zoomStyle(zoomLevel: number) {
  return {
    transform: `scale(${zoomLevel})`,
    transformOrigin: 'top left',
    width: `${100 / zoomLevel}%`,
  } as const;
}

export default function DocumentPreviewRenderer({
  preview,
  title,
  searchQuery,
  zoomLevel,
}: {
  preview: DocumentPreview | null;
  title: string;
  searchQuery: string;
  zoomLevel: number;
}) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const extension = extensionOf(preview, title);
  const text = preview?.preview_text ?? '';
  const viewUrl = preview?.file_url ? apiUrl(preview.file_url) : preview?.open_url ? apiUrl(preview.open_url) : null;
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension);
  const renderedHtml = preview?.rendered_html ?? null;
  const highlightedText = useMemo(() => highlightHtml(text, searchQuery), [searchQuery, text]);

  useEffect(() => {
    const firstHit = containerRef.current?.querySelector('[data-search-hit="true"]');
    if (firstHit instanceof HTMLElement) {
      firstHit.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [highlightedText, preview?.chunk_id, preview?.page, searchQuery]);

  if (!preview) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-[hsl(210_20%_98%)] p-5 text-center text-sm text-muted-foreground">
        Select a citation to load an inline preview.
      </div>
    );
  }

  if (preview.supported_preview === false) {
    return (
      <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
        <FileArchive className="mx-auto text-primary" size={34} />
        <p className="mt-3 text-sm font-semibold text-foreground">Preview not supported</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          This file type does not support inline rendering yet. Metadata and the cited excerpt are still available below.
        </p>
      </div>
    );
  }

  if (preview.render_kind === 'pdf' && viewUrl) {
    const hash = `#page=${preview.page ?? 1}&zoom=${Math.round(zoomLevel * 100)}`;
    return (
      <div className="h-full overflow-hidden rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)]">
        <iframe src={`${viewUrl}${hash}`} title={title} className="h-full w-full" />
      </div>
    );
  }

  if (isImage && viewUrl) {
    return (
      <div className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-4">
        <div style={zoomStyle(zoomLevel)}>
          <img src={viewUrl} alt={title} className="w-full rounded-xl object-contain" />
        </div>
      </div>
    );
  }

  if (preview.render_kind === 'table' || preview.render_kind === 'spreadsheet') {
    return (
      <div className="flex h-full min-h-0 flex-col overflow-hidden rounded-[1.5rem] border border-border bg-white">
        {preview.sheet_names?.length ? (
          <div className="flex flex-wrap gap-2 border-b border-border px-4 py-3">
            {preview.sheet_names.map((sheet) => (
              <span
                key={sheet}
                className={`rounded-full px-2.5 py-1 text-xs font-semibold ${sheet === preview.active_sheet ? 'bg-[hsl(95_24%_94%)] text-primary' : 'bg-[hsl(210_20%_98%)] text-muted-foreground'}`}
              >
                {sheet}
              </span>
            ))}
          </div>
        ) : null}
        <div ref={containerRef} className="scrollbar-soft min-h-0 flex-1 overflow-auto">
          <div style={zoomStyle(zoomLevel)}>
            <table className="min-w-full text-left text-xs">
              <tbody>
                {(preview.table_rows ?? []).map((row, rowIndex) => (
                  <tr
                    key={rowIndex}
                    className={rowIndex === 0 ? 'sticky top-0 bg-[hsl(210_20%_98%)] font-semibold text-slate-900' : 'border-t border-border text-slate-700'}
                  >
                    {row.map((cell, cellIndex) => (
                      <td
                        key={`${rowIndex}-${cellIndex}`}
                        className="max-w-48 px-3 py-2 align-top"
                        dangerouslySetInnerHTML={{ __html: highlightHtml(cell, searchQuery) }}
                      />
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  }

  if (preview.render_kind === 'slides' && preview.slides?.length) {
    const activeSlideIndex = Math.max(0, Math.min((preview.page ?? 1) - 1, preview.slides.length - 1));
    const activeSlide = preview.slides[activeSlideIndex];

    return (
      <div className="grid h-full min-h-0 gap-4 lg:grid-cols-[9rem_minmax(0,1fr)]">
        <div className="scrollbar-soft flex gap-2 overflow-auto lg:flex-col">
          {preview.slides.map((slide, index) => (
            <div
              key={`${slide.index}-${slide.title}`}
              className={`min-w-[7rem] rounded-2xl border p-3 text-left ${index === activeSlideIndex ? 'border-primary bg-[hsl(95_24%_95%)]' : 'border-border bg-white'}`}
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Slide {slide.index}</p>
              <p className="mt-2 line-clamp-2 text-sm font-semibold text-foreground">{slide.title}</p>
            </div>
          ))}
        </div>
        <div className="scrollbar-soft overflow-auto rounded-[1.5rem] border border-border bg-white p-5" ref={containerRef}>
          <div style={zoomStyle(zoomLevel)} className="space-y-4">
            <div className="rounded-[1.25rem] border border-border bg-[linear-gradient(160deg,#fffdf7_0%,#f8fafc_100%)] p-6 shadow-sm">
              <p className="text-xs font-semibold uppercase tracking-[0.08em] text-muted-foreground">Slide {activeSlide.index}</p>
              <h3 className="mt-3 text-2xl font-semibold text-slate-950">{activeSlide.title}</h3>
              <div
                className="safe-text mt-5 whitespace-pre-wrap text-sm leading-7 text-slate-700"
                dangerouslySetInnerHTML={{ __html: highlightHtml(activeSlide.body || 'No speaker notes or body text available for this slide.', searchQuery) }}
              />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if ((preview.render_kind === 'docx' || preview.render_kind === 'markdown' || preview.render_kind === 'html') && renderedHtml) {
    return (
      <div className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-white p-5" ref={containerRef}>
        <article
          className="prose prose-slate max-w-none"
          style={zoomStyle(zoomLevel)}
          dangerouslySetInnerHTML={{ __html: renderedHtml }}
        />
      </div>
    );
  }

  if ((preview.render_kind === 'text' || preview.render_kind === 'code') && text) {
    return (
      <div className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-4" ref={containerRef}>
        <pre
          className="text-xs leading-6 text-slate-800"
          style={zoomStyle(zoomLevel)}
          dangerouslySetInnerHTML={{ __html: highlightedText }}
        />
      </div>
    );
  }

  if (preview.preview_text) {
    return (
      <div className="scrollbar-soft h-full overflow-auto rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-4" ref={containerRef}>
        <div
          className="safe-text whitespace-pre-wrap text-sm leading-7 text-slate-700"
          style={zoomStyle(zoomLevel)}
          dangerouslySetInnerHTML={{ __html: highlightedText }}
        />
      </div>
    );
  }

  const Icon = extension === 'xlsx' || extension === 'csv'
    ? FileSpreadsheet
    : extension === 'pptx' || extension === 'ppt'
      ? Presentation
      : extension === 'json'
        ? FileJson
        : isImage
          ? FileImage
          : FileText;

  return (
    <div className="flex h-full items-center justify-center rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
      <div>
        <Icon className="mx-auto text-primary" size={38} />
        <p className="mt-3 text-sm font-semibold text-foreground">{extension ? extension.toUpperCase() : 'Document'} file</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">Inline preview is limited for this format. Metadata and any cited excerpt are shown below.</p>
      </div>
    </div>
  );
}
