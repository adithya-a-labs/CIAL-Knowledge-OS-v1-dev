import { useEffect, useMemo, useState } from 'react';
import { Search } from 'lucide-react';
import { CONTEXT_DOCUMENTS } from '@/data/assistantData';
import type { ContextDocument } from '@/types/assistant';

interface ContextManagerDialogProps {
  open: boolean;
  selectedIds: string[];
  onApply: (ids: string[]) => void;
  onClose: () => void;
}

const groupOrder = ['Enterprise Documents', 'My Workspace', 'Current Uploads'];

export default function ContextManagerDialog({
  open,
  selectedIds,
  onApply,
  onClose,
}: ContextManagerDialogProps) {
  const [draftSelectedIds, setDraftSelectedIds] = useState<string[]>(selectedIds);
  const [query, setQuery] = useState('');

  useEffect(() => {
    if (open) setDraftSelectedIds(selectedIds);
  }, [open, selectedIds]);

  const filteredDocuments = useMemo(() => {
    const normalizedQuery = query.trim().toLowerCase();
    if (!normalizedQuery) return CONTEXT_DOCUMENTS;
    return CONTEXT_DOCUMENTS.filter((doc) =>
      `${doc.title} ${doc.groupLabel} ${doc.department ?? ''}`.toLowerCase().includes(normalizedQuery)
    );
  }, [query]);

  const groupedDocuments = useMemo(() => {
    return groupOrder.map((groupLabel) => ({
      groupLabel,
      documents: filteredDocuments.filter((doc) => doc.groupLabel === groupLabel),
    }));
  }, [filteredDocuments]);

  if (!open) return null;

  const allDocumentIds = CONTEXT_DOCUMENTS.map((doc) => doc.id);

  const toggleDocument = (document: ContextDocument) => {
    setDraftSelectedIds((current) =>
      current.includes(document.id)
        ? current.filter((id) => id !== document.id)
        : [...current, document.id]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-3" data-testid="context-manager-dialog">
      <div className="flex max-h-[90dvh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-border bg-white shadow-2xl">
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Manage Context</h2>
              <p className="text-xs text-muted-foreground">
                Select documents to ground the next assistant response.
              </p>
            </div>
            <span className="ce-badge ce-badge-accent px-2.5 py-1 text-xs">
              {draftSelectedIds.length} selected
            </span>
          </div>

          <div className="ce-control mt-3 flex items-center gap-2 px-3 py-2">
            <Search size={15} className="text-muted-foreground" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search documents"
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground"
              data-testid="input-context-search"
            />
          </div>

          <div className="mt-3 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => setDraftSelectedIds(allDocumentIds)}
              className="ce-action text-primary"
              data-testid="button-select-all-context"
            >
              Select all
            </button>
            <button
              type="button"
              onClick={() => setDraftSelectedIds([])}
              className="ce-action text-[#8a4c32] hover:bg-[#fff5f0]"
              data-testid="button-clear-context"
            >
              Clear selection
            </button>
          </div>
        </div>

        <div className="scrollbar-soft flex-1 overflow-y-auto p-4">
          {groupedDocuments.map(({ groupLabel, documents }) => (
            <section key={groupLabel} className="mb-4 last:mb-0">
              <h3 className="mb-2 text-[11px] font-bold uppercase text-muted-foreground">
                {groupLabel}
              </h3>
              {documents.length > 0 ? (
                <div className="space-y-2">
                  {documents.map((document) => {
                    const checked = draftSelectedIds.includes(document.id);
                    return (
                      <label
                        key={document.id}
                        className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-white px-3 py-2.5 transition-colors hover:bg-muted"
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggleDocument(document)}
                          className="mt-0.5 h-4 w-4 accent-[#4a7c3f]"
                          data-testid={`checkbox-context-${document.id}`}
                        />
                        <span className="min-w-0">
                          <span className="safe-text block text-sm font-medium text-foreground">
                            {document.title}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {document.department ?? document.sourceType}
                          </span>
                        </span>
                      </label>
                    );
                  })}
                </div>
              ) : (
                <p className="rounded-lg border border-dashed border-border bg-muted px-3 py-3 text-xs text-muted-foreground">
                  No matching documents in this group.
                </p>
              )}
            </section>
          ))}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-border px-4 py-3 sm:flex-row sm:justify-end">
          <button
            type="button"
            onClick={onClose}
            className="ce-action min-h-10 px-4 text-sm"
            data-testid="button-cancel-context"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              onApply(draftSelectedIds);
              onClose();
            }}
            className="ce-action ce-action-primary min-h-10 px-4 text-sm"
            data-testid="button-apply-context"
          >
            Apply context
          </button>
        </div>
      </div>
    </div>
  );
}
