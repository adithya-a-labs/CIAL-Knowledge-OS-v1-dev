import { Folder, FileText, Paperclip, UploadCloud, X } from 'lucide-react';
import type { SelectedContextItem } from '@/api/types';
import type {
  SearchScope,
  UploadedFileContext,
} from '@/types/assistant';

interface ContextChipsProps {
  selectedContextItems: SelectedContextItem[];
  uploadedFiles: UploadedFileContext[];
  searchScope: SearchScope;
  onRemoveContext: (id: string) => void;
  onRemoveFile: (id: string) => void;
  onClearAll?: () => void;
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
  onClearAll,
}: ContextChipsProps) {
  const visibleContext = selectedContextItems.slice(0, 3);
  const hiddenContextCount = Math.max(0, selectedContextItems.length - visibleContext.length);
  const visibleUploads = uploadedFiles.slice(0, 2);
  const hiddenUploadCount = Math.max(0, uploadedFiles.length - visibleUploads.length);
  const hasAnyContext = selectedContextItems.length > 0 || uploadedFiles.length > 0;

  return (
    <div className="border-t border-border bg-white px-4 py-3" data-testid="chat-context-area">
      {!hasAnyContext && (
        <div className="rounded-2xl border border-dashed border-border bg-[hsl(210_20%_98%)] px-3 py-2 text-xs text-muted-foreground">
          No context selected. Responses will use the current scope until documents, folders, or uploads are attached.
        </div>
      )}

      {searchScope === 'current_upload' && uploadedFiles.length === 0 && (
        <div className="mt-2 rounded-2xl border border-[#e4c691] bg-[#fffaf2] px-3 py-2 text-xs font-medium text-[#7c4b0c] first:mt-0">
          Current Upload Only is selected, but no files have been attached yet.
        </div>
      )}

      {hasAnyContext && (
        <div className="space-y-2">
          <div className="flex items-center justify-between gap-3">
            <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              <Paperclip size={12} />
              Attached context
            </div>
            {onClearAll ? (
              <button type="button" onClick={onClearAll} className="text-xs font-medium text-muted-foreground transition hover:text-foreground">
                Clear all
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-2">
          {visibleContext.map((item) => (
            <span
              key={item.id}
              className="ce-chip rounded-full bg-[hsl(210_20%_98%)] pr-1"
            >
              {item.type === 'folder' ? (
                <Folder size={12} className="shrink-0 text-[#8a5b13]" />
              ) : (
                <FileText size={12} className="shrink-0 text-primary" />
              )}
              <span className="safe-text max-w-[13rem] truncate">{item.title}</span>
              <button
                type="button"
                onClick={() => onRemoveContext(item.id)}
                className="rounded-md p-0.5 text-muted-foreground hover:bg-muted hover:text-primary"
                aria-label={`Remove ${item.title}`}
                data-testid={`button-remove-context-${item.id}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}

          {hiddenContextCount > 0 && (
            <span className="ce-chip rounded-full bg-accent text-primary">
              +{hiddenContextCount} more
            </span>
          )}

          {visibleUploads.map((file) => (
            <span
              key={file.id}
              className="ce-chip rounded-full bg-[hsl(210_20%_98%)] pr-1"
            >
              <UploadCloud size={12} className="shrink-0 text-[#346c96]" />
              <span className="safe-text max-w-[12rem] truncate">
                {file.name} ({formatFileSize(file.size)})
              </span>
              <span className="rounded-full bg-white px-1.5 py-0.5 text-[10px] font-semibold text-muted-foreground">
                {file.uploadStatus === 'uploaded' ? 'Ready' : file.uploadStatus === 'upload_failed' ? 'Failed' : 'Uploading'}
              </span>
              <button
                type="button"
                onClick={() => onRemoveFile(file.id)}
                className="rounded-md p-0.5 text-muted-foreground hover:bg-muted hover:text-[#346c96]"
                aria-label={`Remove ${file.name}`}
                data-testid={`button-remove-upload-${file.id}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}

          {hiddenUploadCount > 0 && (
            <span className="ce-chip rounded-full bg-[#eef6fc] text-[#346c96]">
              +{hiddenUploadCount} upload{hiddenUploadCount === 1 ? '' : 's'}
            </span>
          )}
          </div>
        </div>
      )}
    </div>
  );
}
