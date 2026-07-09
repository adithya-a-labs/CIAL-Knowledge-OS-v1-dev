import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useLocation } from 'wouter';
import {
  CheckSquare,
  ChevronRight,
  FileCode2,
  FileImage,
  FileSpreadsheet,
  FileText,
  Folder,
  Grid3X3,
  List,
  RefreshCcw,
  Search,
  Sparkles,
  Upload,
} from 'lucide-react';
import { getCorpusFolder, getCorpusTree, getDocumentThumbnailUrl } from '@/api/client';
import { corpusDocumentToContext, corpusFolderToContext, normalizeCorpusFolderResponse } from '@/api/adapters';
import type { CorpusDocument, CorpusFolder, CorpusFolderResponse, CorpusTreeNode, SelectedContextItem } from '@/api/types';
import { driveFiles, driveFolders } from '@/data/knowledgeDriveData';
import { cn } from '@/lib/utils';

type ExplorerMode = 'browse' | 'select';
type ViewMode = 'grid' | 'list';
type SortMode = 'latest' | 'name' | 'type';

interface CorpusExplorerProps {
  mode: ExplorerMode;
  selectedItems: SelectedContextItem[];
  onSelectionChange: (items: SelectedContextItem[]) => void;
  onApplySelection?: (items: SelectedContextItem[]) => void;
  onCancel?: () => void;
  onUseInAssistant?: (items: SelectedContextItem[]) => void;
  className?: string;
}

function formatDate(value?: string | null) {
  if (!value) return 'Unknown';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleDateString(undefined, { day: '2-digit', month: 'short', year: 'numeric' });
}

function formatBytes(value: number) {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${Math.round(value / 1024)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function statusTooltip(status: string) {
  const map: Record<string, string> = {
    pending: 'Metadata is synced. Vector indexing has not completed yet.',
    indexing: 'This document is currently being indexed.',
    indexed: 'This document is available to grounded assistant retrieval.',
    failed: 'Indexing failed. Metadata and file preview may still be available.',
    deleted: 'This document was removed from the corpus source.',
  };
  return map[status] ?? 'Corpus indexing status.';
}

function fileIcon(file: CorpusDocument) {
  const extension = (file.extension || file.file_type || '').replace('.', '').toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension)) return FileImage;
  if (['csv', 'xlsx', 'xls'].includes(extension)) return FileSpreadsheet;
  if (['json', 'xml', 'yaml', 'yml', 'html', 'md'].includes(extension)) return FileCode2;
  return FileText;
}

function demoFolderResponse(): CorpusFolderResponse {
  const now = new Date().toISOString();
  return {
    folder: { id: 'demo-root', parent_id: null, name: 'Demo data', relative_path: '', depth: 0, document_count: driveFiles.length, subfolder_count: driveFolders.length, last_scanned_at: null },
    folders: driveFolders.slice(0, 6).map((folder) => ({ id: folder.id, parent_id: 'demo-root', name: folder.name, relative_path: folder.name, depth: 1, document_count: folder.itemCount, subfolder_count: 0, last_scanned_at: null })),
    files: driveFiles.slice(0, 12).map((file) => ({
      id: file.id,
      folder_id: 'demo-root',
      name: file.name,
      relative_path: file.name,
      extension: `.${file.previewType}`,
      mime_type: null,
      file_type: file.previewType,
      size_bytes: file.sizeBytes,
      content_hash: null,
      modified_at: now,
      indexed: true,
      indexing_status: 'indexed',
      indexed_at: null,
      page_count: null,
      created_at: now,
      updated_at: now,
    })),
  };
}

function CorpusTree({
  node,
  activePath,
  expanded,
  onToggle,
  onSelect,
  depth = 0,
}: {
  node: CorpusTreeNode;
  activePath: string;
  expanded: Set<string>;
  onToggle: (path: string) => void;
  onSelect: (path: string) => void;
  depth?: number;
}) {
  const path = node.relative_path;
  const isExpanded = path === '' || expanded.has(path);
  const active = activePath === path;

  return (
    <div>
      <button
        type="button"
        onClick={() => {
          onSelect(path);
          if (node.children.length > 0) onToggle(path);
        }}
        className={cn(
          'flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-sm transition-colors hover:bg-slate-100',
          active ? 'bg-[#f0f7ed] font-semibold text-primary' : 'text-slate-600',
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
      >
        {node.children.length > 0 ? <ChevronRight size={14} className={cn('shrink-0 transition-transform', isExpanded && 'rotate-90')} /> : <span className="w-3.5 shrink-0" />}
        <Folder size={15} className="shrink-0" />
        <span className="truncate">{node.name || 'Corpus root'}</span>
      </button>
      {isExpanded &&
        node.children.map((child) => (
          <CorpusTree key={child.id ?? child.relative_path} node={child} activePath={activePath} expanded={expanded} onToggle={onToggle} onSelect={onSelect} depth={depth + 1} />
        ))}
    </div>
  );
}

function FolderCard({
  folder,
  selected,
  selectable,
  onOpen,
  onToggle,
}: {
  folder: CorpusFolder;
  selected: boolean;
  selectable: boolean;
  onOpen: () => void;
  onToggle: () => void;
}) {
  return (
    <article className={cn('rounded-xl border border-slate-200 bg-white p-3 shadow-sm', selected && 'border-primary ring-2 ring-primary/15')}>
      <div className="flex items-start gap-3">
        {selectable ? (
          <input type="checkbox" checked={selected} onChange={onToggle} className="mt-3 h-4 w-4 rounded border-slate-300 text-primary" aria-label={`Select ${folder.name || 'Corpus root'}`} />
        ) : null}
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-amber-50 text-amber-600"><Folder size={21} /></span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-slate-950">{folder.name || 'Corpus root'}</span>
            <span className="block truncate text-xs text-slate-500">{folder.relative_path || 'Root'} / {folder.document_count} files</span>
          </span>
        </button>
      </div>
    </article>
  );
}

function FileCard({
  file,
  selected,
  viewMode,
  selectable,
  onOpen,
  onToggle,
}: {
  file: CorpusDocument;
  selected: boolean;
  viewMode: ViewMode;
  selectable: boolean;
  onOpen: () => void;
  onToggle: () => void;
}) {
  const Icon = fileIcon(file);
  const typeLabel = (file.extension || file.file_type || 'file').replace('.', '').toUpperCase();
  const thumbnailUrl = getDocumentThumbnailUrl(file.id);

  if (viewMode === 'grid') {
    return (
      <article className={cn('rounded-[1.35rem] border border-slate-200 bg-white p-3 shadow-sm transition hover:border-slate-300 hover:shadow-md', selected && 'border-primary ring-2 ring-primary/15')}>
        <div className="flex items-start gap-3">
          {selectable ? (
            <input type="checkbox" checked={selected} onChange={onToggle} className="mt-1 h-4 w-4 rounded border-slate-300 text-primary" aria-label={`Select ${file.name}`} />
          ) : null}
          <button type="button" onClick={onOpen} className="min-w-0 flex-1 text-left">
            <div className="mb-3 aspect-[4/3] overflow-hidden rounded-[1rem] border border-slate-200 bg-slate-50">
              <img src={thumbnailUrl} alt="" loading="lazy" className="h-full w-full object-cover" onError={(event) => { event.currentTarget.style.display = 'none'; }} />
            </div>
            <div className="flex items-start gap-2">
              <Icon size={16} className="mt-0.5 shrink-0 text-primary" />
              <h3 className="line-clamp-2 min-h-10 text-sm font-semibold text-slate-950">{file.name}</h3>
            </div>
            <p className="mt-2 truncate text-xs text-slate-500">{file.relative_path}</p>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
              {file.page_count ? `${file.page_count} pages available for inline preview.` : 'Open to inspect the live document preview and metadata.'}
            </p>
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
          <span className="rounded-full bg-[hsl(210_20%_98%)] px-2 py-1 font-semibold text-slate-700">{typeLabel}</span>
          <span>{formatBytes(file.size_bytes)}</span>
          <span>{formatDate(file.modified_at)}</span>
          <span className="rounded-full bg-[hsl(95_24%_94%)] px-2 py-1 font-semibold text-primary" title={statusTooltip(file.indexing_status)}>{file.indexing_status}</span>
        </div>
      </article>
    );
  }

  return (
    <div className={cn('grid min-w-[48rem] grid-cols-[2rem_minmax(18rem,1fr)_7rem_8rem_8rem_8rem] items-center border-b border-slate-100 px-3 py-2.5 text-sm last:border-b-0 hover:bg-slate-50', selected && 'bg-[#f0f7ed]/80')}>
      {selectable ? <input type="checkbox" checked={selected} onChange={onToggle} className="h-4 w-4 rounded border-slate-300 text-primary" aria-label={`Select ${file.name}`} /> : <span />}
      <button type="button" onClick={onOpen} className="flex min-w-0 items-center gap-3 text-left"><Icon size={16} className="text-primary" /><span className="truncate font-medium text-slate-800">{file.name}</span></button>
      <span>{typeLabel}</span>
      <span>{formatBytes(file.size_bytes)}</span>
      <span>{formatDate(file.modified_at)}</span>
      <span className="font-semibold text-primary" title={statusTooltip(file.indexing_status)}>{file.indexing_status}</span>
    </div>
  );
}

export default function CorpusExplorer({
  mode,
  selectedItems,
  onSelectionChange,
  onApplySelection,
  onCancel,
  onUseInAssistant,
  className,
}: CorpusExplorerProps) {
  const [, navigate] = useLocation();
  const [activePath, setActivePath] = useState('');
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['']));
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [sortMode, setSortMode] = useState<SortMode>('latest');

  const treeQuery = useQuery({ queryKey: ['corpus-tree', mode], queryFn: getCorpusTree, retry: false, staleTime: 30_000 });
  const folderQuery = useQuery({ queryKey: ['corpus-folder', activePath, mode], queryFn: () => getCorpusFolder(activePath), retry: false, staleTime: 30_000 });
  const usingFallback = treeQuery.isError || folderQuery.isError;
  const folderResponse = usingFallback ? demoFolderResponse() : folderQuery.data ? normalizeCorpusFolderResponse(folderQuery.data) : null;
  const root = treeQuery.data?.root;
  const selectedIds = new Set(selectedItems.map((item) => item.id));
  const selectable = mode === 'select' || mode === 'browse';

  const filteredFolders = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const folders = folderResponse?.folders ?? [];
    if (!query) return folders;
    return folders.filter((folder) => `${folder.name} ${folder.relative_path}`.toLowerCase().includes(query));
  }, [folderResponse, searchQuery]);

  const filteredFiles = useMemo(() => {
    const query = searchQuery.trim().toLowerCase();
    const files = [...(folderResponse?.files ?? [])].filter((file) => !query || `${file.name} ${file.relative_path} ${file.file_type}`.toLowerCase().includes(query));
    return files.sort((a, b) => {
      if (sortMode === 'name') return a.name.localeCompare(b.name);
      if (sortMode === 'type') return a.file_type.localeCompare(b.file_type) || a.name.localeCompare(b.name);
      return new Date(b.modified_at ?? 0).getTime() - new Date(a.modified_at ?? 0).getTime();
    });
  }, [folderResponse, searchQuery, sortMode]);

  const selectedDocs = selectedItems.filter((item) => item.type === 'document').length;
  const selectedFolders = selectedItems.filter((item) => item.type === 'folder').length;

  const toggleSelection = (item: SelectedContextItem) => {
    onSelectionChange(
      selectedItems.some((candidate) => candidate.id === item.id)
        ? selectedItems.filter((candidate) => candidate.id !== item.id)
        : [...selectedItems, item],
    );
  };

  const selectVisible = () => {
    const visible = [...filteredFolders.map(corpusFolderToContext), ...filteredFiles.map(corpusDocumentToContext)];
    const merged = new Map(selectedItems.map((item) => [item.id, item]));
    visible.forEach((item) => merged.set(item.id, item));
    onSelectionChange(Array.from(merged.values()));
  };

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden', className)} data-testid={`corpus-explorer-${mode}`}>
      <div className="grid gap-3 xl:grid-cols-[minmax(18rem,1fr)_auto]">
        <label className="relative block min-w-0">
          <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
          <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search Corpus..." className="h-12 w-full rounded-xl border border-slate-200 bg-white px-12 text-sm font-medium text-slate-800 shadow-sm focus:border-primary focus:ring-2 focus:ring-primary/15" data-testid="input-corpus-search" />
        </label>
        <div className="flex flex-wrap items-center gap-2">
          {mode === 'browse' ? (
            <>
              <button type="button" onClick={() => onUseInAssistant?.(selectedItems)} disabled={selectedItems.length === 0} className="ce-action ce-action-primary h-12 px-3 disabled:opacity-50"><Sparkles size={16} />Use in AI Assistant</button>
              <button type="button" className="ce-action h-12 px-3"><Upload size={16} />Upload Document</button>
            </>
          ) : (
            <>
              <button type="button" onClick={selectVisible} className="ce-action h-12 px-3"><CheckSquare size={16} />Select visible</button>
              <button type="button" onClick={() => onSelectionChange([])} className="ce-action h-12 px-3 text-[#8a4c32] hover:bg-[#fff5f0]">Clear</button>
            </>
          )}
          <button type="button" onClick={() => { treeQuery.refetch(); folderQuery.refetch(); }} className="ce-action h-12 px-3" aria-label="Refresh Corpus"><RefreshCcw size={16} />Refresh</button>
        </div>
      </div>

      {usingFallback && <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs font-medium text-amber-900">Backend unavailable. Demo data is shown.</div>}

      <div className="mt-4 flex min-h-0 flex-1 gap-5 overflow-hidden">
        <aside className="hidden w-72 shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:flex xl:flex-col">
          <div className="border-b border-slate-200 p-3 text-sm font-semibold text-slate-900">Corpus Tree</div>
          <div className="scrollbar-soft flex-1 overflow-y-auto p-3">
            {root && !usingFallback ? (
              <CorpusTree node={root} activePath={activePath} expanded={expandedPaths} onToggle={(path) => setExpandedPaths((current) => { const next = new Set(current); next.has(path) ? next.delete(path) : next.add(path); return next; })} onSelect={setActivePath} />
            ) : (
              <p className="text-sm text-slate-500">Corpus tree unavailable.</p>
            )}
          </div>
        </aside>

        <main className="min-w-0 flex-1 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-3 border-b border-slate-200 p-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase text-slate-500">{mode === 'select' ? 'Manage Context' : 'Knowledge Center'}</p>
              <h1 className="safe-text mt-1 truncate text-xl font-semibold text-slate-950">{folderResponse?.folder.name || 'Corpus root'}</h1>
              <p className="safe-text mt-1 truncate text-xs text-slate-500">{folderResponse?.folder.relative_path || 'Root'} / {filteredFolders.length} folders / {filteredFiles.length} files</p>
            </div>
            <div className="flex flex-wrap gap-2">
              <span className="ce-badge ce-badge-accent px-2.5 py-1 text-xs">{selectedDocs} docs / {selectedFolders} folders</span>
              <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className="h-10 rounded-xl border border-slate-200 bg-white px-3 text-sm font-semibold text-slate-700" aria-label="Sort Corpus items">
                <option value="latest">Latest</option>
                <option value="name">Name</option>
                <option value="type">Type</option>
              </select>
              <button type="button" onClick={() => setViewMode('grid')} className={cn('ce-icon-button', viewMode === 'grid' && 'bg-[#f0f7ed] text-primary')} aria-label="Grid view"><Grid3X3 size={16} /></button>
              <button type="button" onClick={() => setViewMode('list')} className={cn('ce-icon-button', viewMode === 'list' && 'bg-[#f0f7ed] text-primary')} aria-label="List view"><List size={16} /></button>
            </div>
          </div>

          <div className="scrollbar-soft h-full overflow-y-auto p-4 pb-28">
            {treeQuery.isLoading || folderQuery.isLoading ? <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-sm text-slate-500">Loading Corpus...</div> : null}
            {filteredFolders.length > 0 && (
              <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {filteredFolders.map((folder) => (
                  <FolderCard key={folder.id ?? folder.relative_path} folder={folder} selected={selectedIds.has(folder.id ?? folder.relative_path)} selectable={selectable} onOpen={() => setActivePath(folder.relative_path)} onToggle={() => toggleSelection(corpusFolderToContext(folder))} />
                ))}
              </div>
            )}
            {filteredFiles.length === 0 && filteredFolders.length === 0 ? (
              <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-10 text-center">
                <Search size={24} className="text-slate-400" />
                <h3 className="mt-3 text-sm font-semibold text-slate-800">No Corpus items found</h3>
                <p className="mt-1 max-w-sm text-sm text-slate-500">Try another folder or search term.</p>
              </div>
            ) : viewMode === 'grid' ? (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
                {filteredFiles.map((file) => (
                  <FileCard key={file.id} file={file} selected={selectedIds.has(file.id)} viewMode="grid" selectable={selectable} onToggle={() => toggleSelection(corpusDocumentToContext(file))} onOpen={() => navigate(`/knowledge/document/${encodeURIComponent(file.id)}`)} />
                ))}
              </div>
            ) : (
              <div className="overflow-x-auto rounded-xl border border-slate-200">
                {filteredFiles.map((file) => (
                  <FileCard key={file.id} file={file} selected={selectedIds.has(file.id)} viewMode="list" selectable={selectable} onToggle={() => toggleSelection(corpusDocumentToContext(file))} onOpen={() => navigate(`/knowledge/document/${encodeURIComponent(file.id)}`)} />
                ))}
              </div>
            )}
          </div>
        </main>
      </div>

      {mode === 'select' ? (
        <div className="mt-3 flex shrink-0 flex-col gap-2 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap gap-2">
            {selectedItems.slice(0, 4).map((item) => (
              <span key={item.id} className="ce-badge max-w-48 truncate px-2.5 py-1 text-xs">{item.title}</span>
            ))}
            {selectedItems.length > 4 ? <span className="ce-badge px-2.5 py-1 text-xs">+{selectedItems.length - 4} more</span> : null}
          </div>
          <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
            <button type="button" onClick={onCancel} className="ce-action min-h-10 px-4 text-sm">Cancel</button>
            <button type="button" onClick={() => onApplySelection?.(selectedItems)} className="ce-action ce-action-primary min-h-10 px-4 text-sm" data-testid="button-apply-context">Apply context</button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
