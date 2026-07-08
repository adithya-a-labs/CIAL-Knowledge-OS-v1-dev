import { FileArchive, FileImage, FileJson, FileSpreadsheet, FileText, Presentation } from 'lucide-react';
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
  const isText = ['txt', 'md', 'markdown', 'html', 'htm', 'json', 'xml', 'yaml', 'yml', 'csv'].includes(extension);
  const isImage = ['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension);

  if (isText && text) {
    return (
      <pre className="scrollbar-soft max-h-[32rem] overflow-auto rounded-xl border border-border bg-[hsl(210_20%_98%)] p-3 text-xs leading-5 text-slate-800">
        {formatPreviewText(text, extension)}
      </pre>
    );
  }

  if (extension === 'pdf') {
    return (
      <div className="rounded-xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
        <FileText className="mx-auto text-red-600" size={36} />
        <p className="mt-3 text-sm font-semibold text-foreground">PDF document</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">Metadata and citation excerpt are available. Inline file streaming can be connected when document serving is enabled.</p>
      </div>
    );
  }

  if (isImage) {
    return (
      <div className="rounded-xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
        <FileImage className="mx-auto text-[#6b5ecf]" size={36} />
        <p className="mt-3 text-sm font-semibold text-foreground">Image document</p>
        <p className="mt-1 text-xs text-muted-foreground">Image streaming is ready to attach when document file serving is enabled.</p>
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
    <div className="rounded-xl border border-border bg-[hsl(210_20%_98%)] p-5 text-center">
      <Icon className="mx-auto text-primary" size={36} />
      <p className="mt-3 text-sm font-semibold text-foreground">{extension ? extension.toUpperCase() : 'Document'} file</p>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">Preview text is not available for this format yet. Use the source excerpt and metadata below.</p>
    </div>
  );
}

