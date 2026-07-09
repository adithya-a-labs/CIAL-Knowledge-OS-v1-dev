import { FileArchive, FileImage, FileJson, FileSpreadsheet, FileText, Presentation } from 'lucide-react';

interface FallbackViewerProps {
  extension: string;
  isImage?: boolean;
  notice?: string | null;
}

export default function FallbackViewer({ extension, isImage = false, notice }: FallbackViewerProps) {
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
    <div className="flex h-full items-center justify-center rounded-[1.5rem] border border-border bg-[hsl(210_20%_98%)] p-6 text-center">
      <div className="max-w-sm">
        {notice ? <Icon className="mx-auto text-primary" size={38} /> : <FileArchive className="mx-auto text-primary" size={34} />}
        <p className="mt-3 text-sm font-semibold text-foreground">{extension ? extension.toUpperCase() : 'Document'} file</p>
        <p className="mt-1 text-xs leading-5 text-muted-foreground">
          {notice || 'Open or download the document to inspect its original layout.'}
        </p>
      </div>
    </div>
  );
}
