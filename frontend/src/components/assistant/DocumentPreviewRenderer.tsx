import { FileArchive, FileImage, FileJson, FileSpreadsheet, FileText, Presentation, ZoomIn } from 'lucide-react';
import { apiUrl } from '@/api/client';
import type { DocumentPreview } from '@/api/types';

function extensionOf(preview: DocumentPreview | null, fallbackTitle: string) {
  return (preview?.extension || fallbackTitle.split('.').pop() || '').replace(/^\./, '').toLowerCase();
}

function formatPreviewText(text: string, extension: string) {
  if (extension === 'json') {
    try {
      return JSON.stringify(JSON.parse(text), null, 2);
    } catch {
      return text;
    }
  }
  return text;
}

export default function DocumentPreviewRenderer({
  preview,
  title,
}: {
  preview: DocumentPreview | null;
  title: string;
}) {
  const extension = extensionOf(preview, title);
  const text = preview?.preview_text ?? '';
  const viewUrl = preview?.file_url ? apiUrl(preview.file_url) : preview?.open_url ? apiUrl(preview.open_url) : null;
  const isText = ['txt', 'md', 'markdown', 'html', 'htm', 'json', 'xml', 'yaml', 'yml'].includes(extension);
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension);

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

  if ((isText || preview.render_kind === 'code') && text) {
    return (
      <pre className="scrollbar-soft max-h-[32rem] overflow-auto rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-4 text-xs leading-6 text-slate-800">
        {formatPreviewText(text, extension)}
      </pre>
    );
  }

  if (preview.render_kind === 'table' && preview.table_rows?.length) {
    return (
      <div className="scrollbar-soft max-h-[28rem] overflow-auto rounded-2xl border border-border bg-white">
        <table className="min-w-full text-left text-xs">
          <tbody>
            {preview.table_rows.map((row, rowIndex) => (
              <tr key={rowIndex} className={rowIndex === 0 ? 'bg-[hsl(210_20%_98%)] font-semibold text-slate-900' : 'border-t border-border text-slate-700'}>
                {row.map((cell, cellIndex) => (
                  <td key={`${rowIndex}-${cellIndex}`} className="max-w-40 truncate px-3 py-2">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  if (extension === 'pdf' && viewUrl) {
    return (
      <div className="h-[32rem] overflow-hidden rounded-2xl border border-border bg-[hsl(210_20%_98%)]">
        <iframe
          src={`${viewUrl}#page=${preview.page ?? 1}`}
          title={title}
          className="h-full w-full"
        />
      </div>
    );
  }

  if (extension === 'pdf') {
    return (
      <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
        <FileText className="mx-auto text-red-600" size={36} />
        <p className="mt-3 text-sm font-semibold text-foreground">PDF preview unavailable</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">The cited excerpt and metadata are available below.</p>
      </div>
    );
  }

  if (isImage && viewUrl) {
    return (
      <a href={viewUrl} target="_blank" rel="noreferrer" className="group block overflow-hidden rounded-2xl border border-border bg-[hsl(210_20%_98%)]">
        <span className="flex items-center justify-end gap-1 border-b border-border px-3 py-2 text-xs font-semibold text-muted-foreground"><ZoomIn size={14} />Open full size</span>
        <img src={viewUrl} alt={title} className="max-h-[32rem] w-full object-contain p-3" />
      </a>
    );
  }

  if (isImage) {
    return (
      <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
        <FileImage className="mx-auto text-[#346c96]" size={36} />
        <p className="mt-3 text-sm font-semibold text-foreground">Image preview unavailable</p>
        <p className="mt-1 text-xs text-muted-foreground">The image metadata and cited excerpt are still available below.</p>
      </div>
    );
  }

  const Icon = extension === 'xlsx' || extension === 'csv'
    ? FileSpreadsheet
    : extension === 'pptx' || extension === 'ppt'
      ? Presentation
      : extension === 'json'
        ? FileJson
        : FileArchive;

  return (
    <div className="rounded-2xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
      <Icon className="mx-auto text-primary" size={36} />
      <p className="mt-3 text-sm font-semibold text-foreground">{extension ? extension.toUpperCase() : 'Document'} file</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">Inline preview is limited for this format. Metadata and any cited excerpt are shown below.</p>
      {viewUrl ? <a href={viewUrl} target="_blank" rel="noreferrer" className="mt-3 inline-flex text-xs font-semibold text-primary">Open preview</a> : null}
    </div>
  );
}
