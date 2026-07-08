import { useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { FileText, Folder, Search } from 'lucide-react';
import { getCorpusTree } from '@/api/client';
import { corpusDocumentToContext, corpusFolderToContext, flattenCorpusTree } from '@/api/adapters';
import type { SelectedContextItem } from '@/api/types';
import { CONTEXT_DOCUMENTS } from '@/data/assistantData';

interface ContextManagerDialogProps {
  open: boolean;
  selectedItems: SelectedContextItem[];
  onApply: (items: SelectedContextItem[]) => void;
  onClose: () => void;
}

export default function ContextManagerDialog({
  open,
  selectedItems,
  onApply,
  onClose,
}: ContextManagerDialogProps) {
  const [draftItems, setDraftItems] = useState<SelectedContextItem[]>(selectedItems);
  const [query, setQuery] = useState('');
  const corpusQuery = useQuery({
    queryKey: ['corpus-tree-context-picker'],
    queryFn: getCorpusTree,
    enabled: open,
    retry: false,
    staleTime: 30_000,
  });

  useEffect(() => {
    if (open) setDraftItems(selectedItems);
  }, [open, selectedItems]);

  const corpusItems = useMemo(() => {
    if (!corpusQuery.data?.root) return [];
    const flattened = flattenCorpusTree(corpusQuery.data.root);
    return [
      ...flattened.folders.filter((folder) => folder.id !== null).map(corpusFolderToContext),
      ...flattened.documents.map(corpusDocumentToContext),
    ];
  }, [corpusQuery.data]);

  const fallbackItems: SelectedContextItem[] = useMemo(
    () =>
      CONTEXT_DOCUMENTS.map((document) => ({
        id: document.id,
        type: 'document',
        title: document.title,
        relative_path: document.department ?? document.groupLabel,
      })),
    [],
  );
  const usingFallback = corpusQuery.isError || (!corpusQuery.isLoading && corpusItems.length === 0);
  const sourceItems = usingFallback ? fallbackItems : corpusItems;
  const normalizedQuery = query.trim().toLowerCase();
  const visibleItems = normalizedQuery
    ? sourceItems.filter((item) => `${item.title} ${item.relative_path}`.toLowerCase().includes(normalizedQuery))
    : sourceItems;
  const selectedIds = new Set(draftItems.map((item) => item.id));
  const selectedFolders = draftItems.filter((item) => item.type === 'folder').length;
  const selectedDocs = draftItems.filter((item) => item.type === 'document').length;

  if (!open) return null;

  const toggleItem = (item: SelectedContextItem) => {
    setDraftItems((current) =>
      current.some((candidate) => candidate.id === item.id)
        ? current.filter((candidate) => candidate.id !== item.id)
        : [...current, item]
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-3" data-testid="context-manager-dialog">
      <div className="flex max-h-[90dvh] w-full max-w-3xl flex-col overflow-hidden rounded-xl border border-border bg-white shadow-2xl">
        <div className="border-b border-border px-4 py-3">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h2 className="text-base font-semibold text-foreground">Manage Context</h2>
              <p className="text-xs text-muted-foreground">
                Browse the Corpus and select folders or documents for the next answer.
              </p>
            </div>
            <span className="ce-badge ce-badge-accent px-2.5 py-1 text-xs">
              {selectedDocs} docs / {selectedFolders} folders
            </span>
          </div>
          {usingFallback && (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">
              Backend unavailable. Demo data is shown.
            </div>
          )}
          <div className="ce-control mt-3 flex items-center gap-2 px-3 py-2">
            <Search size={15} className="text-muted-foreground" />
            <input
              type="search"
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="Search Corpus"
              className="min-w-0 flex-1 bg-transparent text-sm text-foreground placeholder:text-muted-foreground"
              data-testid="input-context-search"
            />
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <button type="button" onClick={() => setDraftItems(visibleItems)} className="ce-action text-primary">
              Select visible
            </button>
            <button type="button" onClick={() => setDraftItems([])} className="ce-action text-[#8a4c32] hover:bg-[#fff5f0]">
              Clear selection
            </button>
          </div>
        </div>

        <div className="scrollbar-soft flex-1 overflow-y-auto p-4">
          {corpusQuery.isLoading ? (
            <p className="rounded-lg border border-border bg-muted px-3 py-3 text-sm text-muted-foreground">Loading Corpus...</p>
          ) : visibleItems.length === 0 ? (
            <p className="rounded-lg border border-dashed border-border bg-muted px-3 py-3 text-xs text-muted-foreground">No matching Corpus items.</p>
          ) : (
            <div className="space-y-2">
              {visibleItems.map((item) => {
                const checked = selectedIds.has(item.id);
                const Icon = item.type === 'folder' ? Folder : FileText;
                return (
                  <label key={item.id} className="flex cursor-pointer items-start gap-3 rounded-lg border border-border bg-white px-3 py-2.5 transition-colors hover:bg-muted">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => toggleItem(item)}
                      className="mt-0.5 h-4 w-4 accent-[#4a7c3f]"
                      data-testid={`checkbox-context-${item.id}`}
                    />
                    <Icon size={16} className="mt-0.5 shrink-0 text-primary" />
                    <span className="min-w-0">
                      <span className="safe-text block text-sm font-medium text-foreground">{item.title}</span>
                      <span className="safe-text text-xs text-muted-foreground">
                        {item.type === 'folder' ? 'Folder' : 'Document'} / {item.relative_path || 'Corpus root'}
                        {item.document_count !== undefined ? ` / ${item.document_count} docs` : ''}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        <div className="flex flex-col-reverse gap-2 border-t border-border px-4 py-3 sm:flex-row sm:justify-end">
          <button type="button" onClick={onClose} className="ce-action min-h-10 px-4 text-sm">
            Cancel
          </button>
          <button
            type="button"
            onClick={() => {
              onApply(draftItems);
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

