import { FileText, UploadCloud, X } from 'lucide-react';
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
}: ContextChipsProps) {
  const visibleContext = selectedContextItems.slice(0, 4);
  const hiddenContextCount = Math.max(0, selectedContextItems.length - visibleContext.length);
  const hasAnyContext = selectedContextItems.length > 0 || uploadedFiles.length > 0;

  return (
    <div className="border-t border-border bg-white px-3 py-2.5 sm:px-4" data-testid="chat-context-area">
      {!hasAnyContext && (
        <div className="rounded-lg border border-dashed border-border bg-muted px-3 py-2 text-xs text-muted-foreground">
          No context selected. Responses will use the selected scope defaults until documents or uploads are added.
        </div>
      )}

      {searchScope === 'current_upload' && uploadedFiles.length === 0 && (
        <div className="mt-2 rounded-lg border border-[#e4c691] bg-[#fffaf2] px-3 py-2 text-xs font-medium text-[#7c4b0c] first:mt-0">
          Current Upload Only is selected, but no files have been attached yet.
        </div>
      )}

      {hasAnyContext && (
        <div className="flex flex-wrap gap-2">
          {visibleContext.map((item) => (
            <span
              key={item.id}
              className="ce-chip"
            >
              <FileText size={12} className="shrink-0 text-primary" />
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
            <span className="ce-chip bg-accent text-primary">
              +{hiddenContextCount} more
            </span>
          )}

          {uploadedFiles.map((file) => (
            <span
              key={file.id}
              className="ce-chip"
            >
              <UploadCloud size={12} className="shrink-0 text-[#346c96]" />
              <span className="safe-text max-w-[12rem] truncate">
                {file.name} ({formatFileSize(file.size)})
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
        </div>
      )}
    </div>
  );
}
