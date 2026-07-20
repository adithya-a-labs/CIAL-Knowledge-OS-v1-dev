import { Folder, FileText, Paperclip, UploadCloud, X } from 'lucide-react';
import FileIndexingStatus from '@/components/documents/FileIndexingStatus';
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
  const showUploadWarning = searchScope === 'current_upload' && uploadedFiles.length === 0;

  if (!hasAnyContext && !showUploadWarning) {
    return null;
  }

  return (
    <div className="space-y-1.5 px-3 pb-1.5 sm:px-4" data-testid="chat-context-area">
      {showUploadWarning && (
        <div className="rounded-md border border-[#e4c691] bg-[#fffaf2] px-2.5 py-1.5 text-[11px] font-medium text-[#7c4b0c]">
          Current Upload Only is selected, but no files have been attached yet.
        </div>
      )}

      {hasAnyContext && (
        <div className="space-y-1.5">
          <div className="flex items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
              <span className="flex items-center gap-2">
                <Paperclip size={12} />
                Attached context
              </span>
              <span className="rounded-sm bg-[#eef5e8] px-1.5 py-0.5 text-[10px] text-primary">
                Hard retrieval boundary
              </span>
            </div>
            {onClearAll ? (
              <button type="button" onClick={onClearAll} className="text-[11px] font-medium text-muted-foreground transition hover:text-foreground">
                Clear all
              </button>
            ) : null}
          </div>

          <div className="flex flex-wrap gap-1.5">
          {visibleContext.map((item) => (
            <span
              key={item.id}
              className="inline-flex items-center gap-1.5 rounded-md border border-[#dce4d8] bg-[#f7faf5] px-2 py-0.5 text-[11px] text-slate-700"
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
                className="rounded-sm p-0.5 text-muted-foreground hover:bg-white hover:text-primary"
                aria-label={`Remove ${item.title}`}
                data-testid={`button-remove-context-${item.id}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}

          {hiddenContextCount > 0 && (
            <span className="inline-flex items-center rounded-md border border-[#dce4d8] bg-[#f1f6ee] px-2 py-0.5 text-[11px] font-medium text-primary">
              +{hiddenContextCount} more
            </span>
          )}

          {visibleUploads.map((file) => (
            <span
              key={file.id}
              className="inline-flex items-center gap-1.5 rounded-md border border-[#d8e5ef] bg-[#f5fafe] px-2 py-0.5 text-[11px] text-slate-700"
            >
              <UploadCloud size={12} className="shrink-0 text-[#346c96]" />
              <span className="safe-text max-w-[12rem] truncate">
                {file.name} ({formatFileSize(file.size)})
              </span>
              <FileIndexingStatus status={file.uploadStatus === 'upload_failed' ? 'failed' : file.uploadStatus === 'uploading' ? 'pending' : file.indexingStatus || 'pending'}
                stage={file.indexingStage} safeMessage={file.indexingSafeMessage} retryAllowed={file.uploadStatus === 'uploaded' && file.retryAllowed}
                documentId={file.backendDocumentId} fileName={file.name} />
              <button
                type="button"
                onClick={() => onRemoveFile(file.id)}
                className="rounded-sm p-0.5 text-muted-foreground hover:bg-white hover:text-[#346c96]"
                aria-label={`Remove ${file.name}`}
                data-testid={`button-remove-upload-${file.id}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}

          {hiddenUploadCount > 0 && (
            <span className="inline-flex items-center rounded-md border border-[#d8e5ef] bg-[#eef6fc] px-2 py-0.5 text-[11px] font-medium text-[#346c96]">
              +{hiddenUploadCount} upload{hiddenUploadCount === 1 ? '' : 's'}
            </span>
          )}
          </div>
        </div>
      )}
    </div>
  );
}
