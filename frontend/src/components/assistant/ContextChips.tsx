import { useState } from 'react';
import { ChevronDown, FileText, Folder, NotebookPen, Settings2, ShieldCheck, UploadCloud, X } from 'lucide-react';
import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import FileIndexingStatus from '@/components/documents/FileIndexingStatus';
import type { SelectedContextItem } from '@/api/types';
import type { SearchScope, UploadedFileContext } from '@/types/assistant';

interface ContextChipsProps {
  selectedContextItems: SelectedContextItem[];
  uploadedFiles: UploadedFileContext[];
  searchScope: SearchScope;
  onRemoveContext: (id: string) => void;
  onRemoveFile: (id: string) => void;
  onManageContext: () => void;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ContextChips({
  selectedContextItems,
  uploadedFiles,
  searchScope,
  onRemoveContext,
  onRemoveFile,
  onManageContext,
}: ContextChipsProps) {
  const [open, setOpen] = useState(false);
  const totalContextCount = selectedContextItems.length + uploadedFiles.length;
  const hasAnyContext = totalContextCount > 0;
  const showUploadWarning = searchScope === 'current_upload' && uploadedFiles.length === 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className="inline-flex h-8 shrink-0 items-center gap-2 rounded-lg px-2 text-sm font-medium text-foreground transition hover:bg-accent hover:text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
          aria-label={`Manage selected context: ${totalContextCount} item${totalContextCount === 1 ? '' : 's'}`}
          data-testid="button-context-selector"
        >
          <ShieldCheck size={17} className="text-primary" />
          <span>{totalContextCount} item{totalContextCount === 1 ? '' : 's'}</span>
          <ChevronDown size={14} className="text-muted-foreground" />
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" side="top" sideOffset={10} className="w-[min(calc(100vw-2rem),23rem)] rounded-xl border-popover-border bg-popover p-0 shadow-lg" data-testid="context-selector-popover">
        <div className="flex items-start justify-between gap-3 border-b border-border px-4 py-3">
          <div>
            <p className="text-sm font-semibold text-foreground">Selected context</p>
            <p className="mt-0.5 text-[11px] leading-4 text-muted-foreground">Selected items form a hard retrieval boundary.</p>
          </div>
          <ShieldCheck size={17} className="mt-0.5 shrink-0 text-primary" aria-hidden="true" />
        </div>

        <div className="max-h-64 overflow-y-auto p-2">
          {showUploadWarning ? (
            <p className="mb-2 rounded-lg bg-warning/10 px-3 py-2 text-xs text-warning-foreground">Attach a file to use Current Upload Only.</p>
          ) : null}
          {!hasAnyContext ? (
            <p className="px-2 py-5 text-center text-sm text-muted-foreground">No documents, folders, or notes selected.</p>
          ) : null}

          {selectedContextItems.map((item) => (
            <div key={item.id} className="flex min-w-0 items-center gap-2 rounded-lg px-2 py-2 hover:bg-muted" data-testid="context-selector-item">
              {item.type === 'folder' ? <Folder size={15} className="shrink-0 text-[#8a5b13]" /> : item.type === 'note' ? <NotebookPen size={15} className="shrink-0 text-primary" /> : <FileText size={15} className="shrink-0 text-primary" />}
              <span className="min-w-0 flex-1 truncate text-sm text-foreground">{item.title}</span>
              <button
                type="button"
                onClick={() => onRemoveContext(item.id)}
                className="ce-icon-button h-7 min-h-7 w-7 min-w-7"
                aria-label={`Remove ${item.title}`}
                data-testid={`button-remove-context-${item.id}`}
              >
                <X size={13} />
              </button>
            </div>
          ))}

          {uploadedFiles.map((file) => (
            <div key={file.id} className="flex min-w-0 items-center gap-2 rounded-lg px-2 py-2 hover:bg-muted" data-testid="context-selector-upload">
              <UploadCloud size={15} className="shrink-0 text-info-foreground" />
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm text-foreground">{file.name}</span>
                <span className="block text-[10px] text-muted-foreground">{formatFileSize(file.size)}</span>
              </span>
              <FileIndexingStatus
                status={file.uploadStatus === 'upload_failed' ? 'failed' : file.uploadStatus === 'uploading' ? 'pending' : file.indexingStatus || 'pending'}
                stage={file.indexingStage}
                safeMessage={file.indexingSafeMessage}
                retryAllowed={file.uploadStatus === 'uploaded' && file.retryAllowed}
                documentId={file.backendDocumentId}
                fileName={file.name}
              />
              <button
                type="button"
                onClick={() => onRemoveFile(file.id)}
                className="ce-icon-button h-7 min-h-7 w-7 min-w-7"
                aria-label={`Remove ${file.name}`}
                data-testid={`button-remove-upload-${file.id}`}
              >
                <X size={13} />
              </button>
            </div>
          ))}
        </div>

        <div className="border-t border-border p-2">
          <button
            type="button"
            onClick={() => {
              setOpen(false);
              onManageContext();
            }}
            className="flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium text-primary transition hover:bg-accent focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring"
            data-testid="button-manage-context"
          >
            <Settings2 size={15} />
            Manage context
          </button>
        </div>
      </PopoverContent>
    </Popover>
  );
}
