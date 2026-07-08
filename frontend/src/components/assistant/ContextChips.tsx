import { FileText, UploadCloud, X } from 'lucide-react';
import type {
  ContextDocument,
  SearchScope,
  UploadedFileContext,
} from '@/types/assistant';

interface ContextChipsProps {
  selectedDocuments: ContextDocument[];
  uploadedFiles: UploadedFileContext[];
  searchScope: SearchScope;
  onRemoveDocument: (id: string) => void;
  onRemoveFile: (id: string) => void;
}

function formatFileSize(size: number) {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${Math.round(size / 1024)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

export default function ContextChips({
  selectedDocuments,
  uploadedFiles,
  searchScope,
  onRemoveDocument,
  onRemoveFile,
}: ContextChipsProps) {
  const visibleDocuments = selectedDocuments.slice(0, 3);
  const hiddenDocumentCount = Math.max(0, selectedDocuments.length - visibleDocuments.length);
  const hasAnyContext = selectedDocuments.length > 0 || uploadedFiles.length > 0;

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
          {visibleDocuments.map((document) => (
            <span
              key={document.id}
              className="ce-chip"
            >
              <FileText size={12} className="shrink-0 text-primary" />
              <span className="safe-text max-w-[13rem] truncate">{document.title}</span>
              <button
                type="button"
                onClick={() => onRemoveDocument(document.id)}
                className="rounded-md p-0.5 text-muted-foreground hover:bg-muted hover:text-primary"
                aria-label={`Remove ${document.title}`}
                data-testid={`button-remove-context-${document.id}`}
              >
                <X size={12} />
              </button>
            </span>
          ))}

          {hiddenDocumentCount > 0 && (
            <span className="ce-chip bg-accent text-primary">
              +{hiddenDocumentCount} more
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
