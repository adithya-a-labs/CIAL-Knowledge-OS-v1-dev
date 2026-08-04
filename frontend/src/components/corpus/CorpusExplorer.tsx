import { useEffect, useMemo, useState } from 'react';
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
  PanelLeftClose,
  PanelLeftOpen,
  RefreshCcw,
  Search,
  Sparkles,
  Upload,
} from 'lucide-react';
import { getCorpusFolder, getCorpusTree, getDocumentThumbnailUrl } from '@/api/client';
import { corpusDocumentToContext, corpusFolderToContext, normalizeCorpusFolderResponse } from '@/api/adapters';
import type { CorpusDocument, CorpusFolder, CorpusTreeNode, SelectedContextItem } from '@/api/types';
import { Checkbox } from '@/components/ui/checkbox';
import FileIndexingStatus from '@/components/documents/FileIndexingStatus';
import { cn } from '@/lib/utils';

type ExplorerMode = 'browse' | 'select';
type ViewMode = 'grid' | 'list';
type SortMode = 'latest' | 'name' | 'type';

export interface CorpusSelectionSummary {
  selectedEntities: number;
  selectedDocuments: number;
  selectedFolders: number;
  resolvedDocuments: CorpusDocument[];
  newDocuments: CorpusDocument[];
  alreadyAttachedCount: number;
  unavailableCount: number;
}

interface CorpusExplorerProps {
  mode: ExplorerMode;
  selectedItems: SelectedContextItem[];
  onSelectionChange: (items: SelectedContextItem[]) => void;
  onApplySelection?: (items: SelectedContextItem[]) => void;
  onCancel?: () => void;
  onUseInAssistant?: (items: SelectedContextItem[]) => void;
  onOpenDocument?: (document: CorpusDocument, trigger: HTMLElement) => void;
  onSelectionSummaryChange?: (summary: CorpusSelectionSummary) => void;
  attachedDocumentIds?: ReadonlySet<string>;
  showSelectionFooter?: boolean;
  embedded?: boolean;
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

function fileIcon(file: CorpusDocument) {
  const extension = (file.extension || file.file_type || '').replace('.', '').toLowerCase();
  if (['png', 'jpg', 'jpeg', 'gif', 'webp', 'bmp', 'tif', 'tiff'].includes(extension)) return FileImage;
  if (['csv', 'xlsx', 'xls'].includes(extension)) return FileSpreadsheet;
  if (['json', 'xml', 'yaml', 'yml', 'html', 'md'].includes(extension)) return FileCode2;
  return FileText;
}

function contextKey(item: SelectedContextItem) {
  return `${item.type}:${item.id}`;
}

function collectDocuments(node: CorpusTreeNode): CorpusDocument[] {
  return [
    ...(node.documents ?? node.files ?? []),
    ...node.children.flatMap(collectDocuments),
  ];
}

function findTreeNode(root: CorpusTreeNode, item: SelectedContextItem | CorpusFolder): CorpusTreeNode | null {
  if ((item.id && root.id === item.id) || root.relative_path === item.relative_path) return root;
  for (const child of root.children) {
    const match = findTreeNode(child, item);
    if (match) return match;
  }
  return null;
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
          'flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-sm transition-colors hover:bg-muted',
          active ? 'bg-accent font-semibold text-primary' : 'text-muted-foreground',
        )}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        aria-expanded={node.children.length > 0 ? isExpanded : undefined}
      >
        {node.children.length > 0 ? <ChevronRight size={14} className={cn('shrink-0 transition-transform', isExpanded && 'rotate-90')} /> : <span className="w-3.5 shrink-0" />}
        <Folder size={15} className="shrink-0" />
        <span className="truncate">{node.name || 'Corpus root'}</span>
      </button>
      {isExpanded && node.children.map((child) => (
        <CorpusTree key={child.id ?? child.relative_path} node={child} activePath={activePath} expanded={expanded} onToggle={onToggle} onSelect={onSelect} depth={depth + 1} />
      ))}
    </div>
  );
}

function FolderCard({
  folder,
  checked,
  disabled,
  resolvedDocumentCount,
  statusText,
  onOpen,
  onToggle,
}: {
  folder: CorpusFolder;
  checked: boolean | 'indeterminate';
  disabled: boolean;
  resolvedDocumentCount: number;
  statusText?: string;
  onOpen: () => void;
  onToggle: () => void;
}) {
  return (
    <article className={cn('rounded-xl border border-border bg-card p-3 shadow-sm', checked === true && 'border-primary ring-2 ring-primary/15')}>
      <div className="flex items-start gap-3">
        <Checkbox checked={checked} disabled={disabled} onCheckedChange={onToggle} className="mt-3" aria-label={`Select folder ${folder.name || 'Corpus root'}`} />
        <button type="button" onClick={onOpen} className="flex min-w-0 flex-1 items-center gap-3 text-left">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-warning/10 text-warning"><Folder size={21} /></span>
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-foreground">{folder.name || 'Corpus root'}</span>
            <span className="block truncate text-xs text-muted-foreground">{resolvedDocumentCount} descendant documents</span>
            <span className="mt-1 block text-[11px] leading-4 text-muted-foreground">{statusText ?? 'Select to attach authorized descendant documents as references.'}</span>
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
  checkboxVisible,
  disabled,
  attached,
  compact,
  onOpen,
  onToggle,
}: {
  file: CorpusDocument;
  selected: boolean;
  viewMode: ViewMode;
  checkboxVisible: boolean;
  disabled: boolean;
  attached: boolean;
  compact: boolean;
  onOpen: (trigger: HTMLElement) => void;
  onToggle: () => void;
}) {
  const Icon = fileIcon(file);
  const typeLabel = (file.extension || file.file_type || 'file').replace('.', '').toUpperCase();
  const thumbnailUrl = getDocumentThumbnailUrl(file.id);
  const selectionControl = checkboxVisible ? (
    <Checkbox checked={attached || selected} disabled={disabled || attached} onCheckedChange={onToggle} className="mt-1" aria-label={`Select document ${file.name}`} />
  ) : null;
  const status = attached ? <span className="rounded-full bg-muted px-2 py-1 text-[11px] font-semibold text-muted-foreground">Already attached</span> : (
    <FileIndexingStatus status={file.indexing_status} stage={file.indexing_stage} safeMessage={file.indexing_safe_message}
      retryAllowed={file.retry_allowed} documentId={file.id} fileName={file.name} />
  );

  if (viewMode === 'grid') {
    return (
      <article className={cn('rounded-[1.35rem] border border-border bg-card p-3 shadow-sm transition hover:shadow-md', selected && 'border-primary ring-2 ring-primary/15', attached && 'bg-muted/40')}>
        <div className="flex items-start gap-3">
          {selectionControl}
          <button type="button" data-source-preview-id={file.id} onClick={(event) => onOpen(event.currentTarget)} className="min-w-0 flex-1 text-left">
            <div className="mb-3 aspect-[4/3] overflow-hidden rounded-[1rem] border border-border bg-muted">
              <img src={thumbnailUrl} alt="" loading="lazy" className="h-full w-full object-cover" onError={(event) => { event.currentTarget.style.display = 'none'; }} />
            </div>
            <div className="flex items-start gap-2">
              <Icon size={16} className="mt-0.5 shrink-0 text-primary" />
              <h3 className="line-clamp-2 min-h-10 text-sm font-semibold text-foreground">{file.name}</h3>
            </div>
            <p className="mt-2 truncate text-xs text-muted-foreground" title={file.relative_path}>{file.relative_path || 'Corpus root'}</p>
            <p className="mt-2 line-clamp-2 text-xs leading-5 text-muted-foreground">
              {file.page_count ? `${file.page_count} pages available for inline preview.` : 'Open to inspect the live document preview and metadata.'}
            </p>
          </button>
        </div>
        <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
          <span className="rounded-full bg-muted px-2 py-1 font-semibold text-foreground">{typeLabel}</span>
          <span>{formatBytes(file.size_bytes)}</span>
          <span>{formatDate(file.modified_at)}</span>
          {file.page_count ? <span>{file.page_count} pages</span> : null}
          {status}
        </div>
      </article>
    );
  }

  if (compact) {
    return (
      <article className={cn('flex w-full items-start gap-3 border-b border-border px-3 py-3 last:border-b-0 hover:bg-muted', selected && 'bg-accent/80', attached && 'bg-muted/40')}>
        {selectionControl ?? <span className="w-4 shrink-0" />}
        <button type="button" data-source-preview-id={file.id} onClick={(event) => onOpen(event.currentTarget)} className="flex min-w-0 flex-1 items-start gap-3 text-left">
          <Icon size={17} className="mt-0.5 shrink-0 text-primary" />
          <span className="min-w-0 flex-1">
            <span className="block break-words text-sm font-medium text-foreground">{file.name}</span>
            <span className="mt-1 block truncate text-xs text-muted-foreground" title={file.relative_path}>{file.relative_path || 'Corpus root'}</span>
            <span className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
              <span className="font-semibold text-foreground">{typeLabel}</span><span>{formatBytes(file.size_bytes)}</span><span>{formatDate(file.modified_at)}</span>{file.page_count ? <span>{file.page_count} pages</span> : null}{status}
            </span>
          </span>
        </button>
      </article>
    );
  }

  return (
    <div className={cn('grid min-w-[48rem] grid-cols-[2rem_minmax(18rem,1fr)_7rem_8rem_8rem_8rem] items-center border-b border-border px-3 py-2.5 text-sm last:border-b-0 hover:bg-muted', selected && 'bg-accent/80')}>
      {selectionControl ?? <span />}
      <button type="button" data-source-preview-id={file.id} onClick={(event) => onOpen(event.currentTarget)} className="flex min-w-0 items-center gap-3 text-left"><Icon size={16} className="text-primary" /><span className="truncate font-medium text-foreground">{file.name}</span></button>
      <span>{typeLabel}</span><span>{formatBytes(file.size_bytes)}</span><span>{formatDate(file.modified_at)}</span>{status}
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
  onOpenDocument,
  onSelectionSummaryChange,
  attachedDocumentIds = new Set<string>(),
  showSelectionFooter = true,
  embedded = false,
  className,
}: CorpusExplorerProps) {
  const [, navigate] = useLocation();
  const [activePath, setActivePath] = useState('');
  const [expandedPaths, setExpandedPaths] = useState<Set<string>>(new Set(['']));
  const [searchQuery, setSearchQuery] = useState('');
  const [viewMode, setViewMode] = useState<ViewMode>('grid');
  const [sortMode, setSortMode] = useState<SortMode>('latest');
  const [treeOpen, setTreeOpen] = useState(true);
  const [mobileFoldersOpen, setMobileFoldersOpen] = useState(false);

  const treeQuery = useQuery({ queryKey: ['corpus-tree'], queryFn: getCorpusTree, retry: false, staleTime: 30_000 });
  const folderQuery = useQuery({ queryKey: ['corpus-folder', activePath], queryFn: () => getCorpusFolder(activePath), retry: false, staleTime: 30_000,
    refetchInterval: (query) => query.state.data && normalizeCorpusFolderResponse(query.state.data).files.some((file) => ['pending', 'indexing'].includes(file.indexing_status)) ? 1500 : false });
  const folderResponse = folderQuery.data ? normalizeCorpusFolderResponse(folderQuery.data) : null;
  const root = treeQuery.data?.root;
  const selectedKeys = new Set(selectedItems.map(contextKey));
  const selectable = mode === 'select' || mode === 'browse';

  const selectionSummary = useMemo<CorpusSelectionSummary>(() => {
    const documentsById = new Map((root ? collectDocuments(root) : []).map((document) => [document.id, document]));
    const resolved = new Map<string, CorpusDocument>();
    for (const item of selectedItems) {
      if (item.type === 'document') {
        const document = documentsById.get(item.id);
        if (document) resolved.set(document.id, document);
      } else if (item.type === 'folder' && root) {
        const node = findTreeNode(root, item);
        if (node) collectDocuments(node).forEach((document) => resolved.set(document.id, document));
      }
    }
    const resolvedDocuments = Array.from(resolved.values());
    const alreadyAttachedCount = resolvedDocuments.filter((document) => attachedDocumentIds.has(document.id)).length;
    const unavailableCount = resolvedDocuments.filter((document) => document.indexing_status !== 'indexed').length;
    const newDocuments = resolvedDocuments.filter((document) => document.indexing_status === 'indexed' && !attachedDocumentIds.has(document.id));
    return {
      selectedEntities: selectedItems.length,
      selectedDocuments: selectedItems.filter((item) => item.type === 'document').length,
      selectedFolders: selectedItems.filter((item) => item.type === 'folder').length,
      resolvedDocuments,
      newDocuments,
      alreadyAttachedCount,
      unavailableCount,
    };
  }, [attachedDocumentIds, root, selectedItems]);

  useEffect(() => onSelectionSummaryChange?.(selectionSummary), [onSelectionSummaryChange, selectionSummary]);

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

  const toggleSelection = (item: SelectedContextItem) => {
    const key = contextKey(item);
    onSelectionChange(selectedKeys.has(key) ? selectedItems.filter((candidate) => contextKey(candidate) !== key) : [...selectedItems, item]);
  };

  const selectVisible = () => {
    const eligibleFiles = filteredFiles.filter((file) => file.indexing_status === 'indexed' && !attachedDocumentIds.has(file.id));
    const visible = [...filteredFolders.map(corpusFolderToContext), ...eligibleFiles.map(corpusDocumentToContext)];
    const merged = new Map(selectedItems.map((item) => [contextKey(item), item]));
    visible.forEach((item) => merged.set(contextKey(item), item));
    onSelectionChange(Array.from(merged.values()));
  };

  const selectPath = (path: string) => {
    setActivePath(path);
    setMobileFoldersOpen(false);
  };

  const openDocument = (document: CorpusDocument, trigger: HTMLElement) => {
    if (onOpenDocument) onOpenDocument(document, trigger);
    else navigate(`/knowledge/document/${encodeURIComponent(document.id)}`);
  };

  const breadcrumbs = useMemo(() => {
    const segments = activePath.split(/[\\/]/).filter(Boolean);
    return segments.map((label, index) => ({ label, path: segments.slice(0, index + 1).join('/') }));
  }, [activePath]);

  const tree = root ? (
    <CorpusTree node={root} activePath={activePath} expanded={expandedPaths} onToggle={(path) => setExpandedPaths((current) => {
      const next = new Set(current); next.has(path) ? next.delete(path) : next.add(path); return next;
    })} onSelect={selectPath} />
  ) : <p className="text-sm text-muted-foreground">Corpus tree unavailable.</p>;

  return (
    <div className={cn('flex h-full min-h-0 flex-col overflow-hidden', className)} data-testid={`corpus-explorer-${mode}`} data-embedded={embedded ? 'true' : 'false'}>
      <div className={cn('grid shrink-0 gap-3', embedded ? 'p-3 lg:grid-cols-[minmax(16rem,1fr)_auto]' : 'xl:grid-cols-[minmax(18rem,1fr)_auto]')}>
        <label className="relative block min-w-0">
          <Search size={18} className="absolute left-4 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input value={searchQuery} onChange={(event) => setSearchQuery(event.target.value)} placeholder="Search Corpus..." className={cn('w-full rounded-xl border border-border bg-card px-11 text-sm font-medium text-foreground shadow-sm focus:border-primary focus:ring-2 focus:ring-primary/15', embedded ? 'h-10' : 'h-12')} data-testid="input-corpus-search" />
        </label>
        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {embedded ? <>
            <button type="button" onClick={() => setMobileFoldersOpen((value) => !value)} className="ce-action h-10 px-3 lg:hidden" aria-expanded={mobileFoldersOpen}><Folder size={16} />Folders</button>
            <button type="button" onClick={() => setTreeOpen((value) => !value)} className="ce-action hidden h-10 px-3 lg:inline-flex" aria-label="Toggle corpus tree" aria-expanded={treeOpen}>{treeOpen ? <PanelLeftClose size={16} /> : <PanelLeftOpen size={16} />}Tree</button>
          </> : null}
          {mode === 'browse' ? <>
            <button type="button" onClick={() => onUseInAssistant?.(selectedItems)} disabled={selectedItems.length === 0} className={cn('ce-action ce-action-primary px-3 disabled:opacity-50', embedded ? 'h-10' : 'h-12')}><Sparkles size={16} />Use in AI Assistant</button>
            <button type="button" onClick={() => navigate('/workspace/documents')} className={cn('ce-action px-3', embedded ? 'h-10' : 'h-12')}><Upload size={16} />Upload Document</button>
          </> : <>
            <button type="button" onClick={selectVisible} className="ce-action h-10 px-3"><CheckSquare size={16} />Select visible</button>
            <button type="button" onClick={() => onSelectionChange([])} className="ce-action h-10 px-3 text-destructive hover:bg-destructive/10">Clear</button>
          </>}
          <button type="button" onClick={() => { void treeQuery.refetch(); void folderQuery.refetch(); }} className={cn('ce-action px-3', embedded ? 'h-10' : 'h-12')} aria-label="Refresh Corpus"><RefreshCcw size={16} /><span className={embedded ? 'sr-only xl:not-sr-only' : ''}>Refresh</span></button>
        </div>
      </div>

      {(treeQuery.isError || folderQuery.isError) ? <div className="mx-3 shrink-0 rounded-lg border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs font-medium text-destructive">The local knowledge service is unavailable. Retry when the backend is ready.</div> : null}

      <div className={cn('flex min-h-0 flex-1 overflow-hidden', embedded ? 'gap-0 border-t border-border' : 'mt-4 gap-5')}>
        {treeOpen ? <aside className={cn('shrink-0 overflow-hidden border-border bg-card shadow-sm', embedded ? 'hidden w-64 border-r lg:flex lg:flex-col xl:w-72' : 'hidden w-72 rounded-2xl border xl:flex xl:flex-col')} data-testid="corpus-tree-panel">
          <div className="shrink-0 border-b border-border p-3 text-sm font-semibold text-foreground">Corpus Tree</div>
          <div className="scrollbar-soft min-h-0 flex-1 overflow-y-auto p-3">{tree}</div>
        </aside> : null}

        {embedded && mobileFoldersOpen ? <section className="scrollbar-soft min-w-0 flex-1 overflow-y-auto bg-card p-3 lg:hidden" aria-label="Corpus folders">{tree}</section> : (
          <main className={cn('min-w-0 flex-1 overflow-hidden bg-card shadow-sm', embedded ? '' : 'rounded-2xl border border-border')}>
            <div className="flex shrink-0 flex-col gap-3 border-b border-border p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="text-xs font-semibold uppercase text-muted-foreground">{mode === 'select' ? 'Select Knowledge Center sources' : 'Knowledge Center'}</p>
                <h1 className="safe-text mt-1 truncate text-xl font-semibold text-foreground">{folderResponse?.folder.name || 'Corpus root'}</h1>
                <nav className="mt-1 flex min-w-0 items-center gap-1 overflow-hidden text-xs text-muted-foreground" aria-label="Corpus breadcrumbs">
                  <button type="button" className="shrink-0 hover:text-primary" onClick={() => selectPath('')}>Root</button>
                  {breadcrumbs.map((crumb) => <span key={crumb.path} className="flex min-w-0 items-center gap-1"><ChevronRight size={11} className="shrink-0" /><button type="button" className="truncate hover:text-primary" onClick={() => selectPath(crumb.path)}>{crumb.label}</button></span>)}
                  <span className="ml-1 shrink-0">/ {filteredFolders.length} folders / {filteredFiles.length} files</span>
                </nav>
              </div>
              <div className="flex flex-wrap gap-2">
                <span className="ce-badge ce-badge-accent px-2.5 py-1 text-xs">{selectionSummary.selectedDocuments} docs / {selectionSummary.selectedFolders} folders</span>
                <select value={sortMode} onChange={(event) => setSortMode(event.target.value as SortMode)} className="h-10 rounded-xl border border-border bg-card px-3 text-sm font-semibold text-foreground" aria-label="Sort Corpus items">
                  <option value="latest">Latest</option><option value="name">Name</option><option value="type">Type</option>
                </select>
                <button type="button" onClick={() => setViewMode('grid')} className={cn('ce-icon-button', viewMode === 'grid' && 'bg-accent text-primary')} aria-label="Grid view"><Grid3X3 size={16} /></button>
                <button type="button" onClick={() => setViewMode('list')} className={cn('ce-icon-button', viewMode === 'list' && 'bg-accent text-primary')} aria-label="List view"><List size={16} /></button>
              </div>
            </div>

            <div className="scrollbar-soft h-full overflow-y-auto p-3 pb-28 sm:p-4 sm:pb-28" data-testid="corpus-folder-contents">
              {treeQuery.isLoading || folderQuery.isLoading ? <div className="rounded-xl border border-border bg-muted p-4 text-sm text-muted-foreground">Loading Corpus...</div> : null}
              {filteredFolders.length > 0 ? <div className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
                {filteredFolders.map((folder) => {
                  const folderItem = corpusFolderToContext(folder);
                  const explicitlySelected = selectedKeys.has(contextKey(folderItem));
                  const node = root ? findTreeNode(root, folder) : null;
                  const descendants = node ? collectDocuments(node) : [];
                  const descendantIds = new Set(descendants.map((document) => document.id));
                  const someDescendantSelected = selectionSummary.resolvedDocuments.some((document) => descendantIds.has(document.id));
                  const eligibleCount = descendants.filter((document) => document.indexing_status === 'indexed' && !attachedDocumentIds.has(document.id)).length;
                  const attachedCount = descendants.filter((document) => attachedDocumentIds.has(document.id)).length;
  const disabled = descendants.length === 0 || eligibleCount === 0;
                  return <FolderCard key={folder.id ?? folder.relative_path} folder={folder} checked={explicitlySelected ? true : someDescendantSelected ? 'indeterminate' : false} disabled={disabled} resolvedDocumentCount={descendants.length}
                    statusText={eligibleCount === 0 && attachedCount > 0 ? 'All authorized descendants are already attached.' : undefined}
                    onOpen={() => selectPath(folder.relative_path)} onToggle={() => toggleSelection(folderItem)} />;
                })}
              </div> : null}
              {filteredFiles.length === 0 && filteredFolders.length === 0 ? <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card px-4 py-10 text-center">
                <Search size={24} className="text-muted-foreground" /><h3 className="mt-3 text-sm font-semibold text-foreground">No Corpus items found</h3><p className="mt-1 max-w-sm text-sm text-muted-foreground">Try another folder or search term.</p>
              </div> : viewMode === 'grid' ? <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
                {filteredFiles.map((file) => <FileCard key={file.id} file={file} selected={selectedKeys.has(contextKey(corpusDocumentToContext(file)))} viewMode="grid" checkboxVisible={selectable}
                  disabled={file.indexing_status !== 'indexed'} attached={attachedDocumentIds.has(file.id)} compact={embedded} onToggle={() => toggleSelection(corpusDocumentToContext(file))} onOpen={(trigger) => openDocument(file, trigger)} />)}
              </div> : <div className="overflow-hidden rounded-xl border border-border">
                {filteredFiles.map((file) => <FileCard key={file.id} file={file} selected={selectedKeys.has(contextKey(corpusDocumentToContext(file)))} viewMode="list" checkboxVisible={selectable}
                  disabled={file.indexing_status !== 'indexed'} attached={attachedDocumentIds.has(file.id)} compact={embedded} onToggle={() => toggleSelection(corpusDocumentToContext(file))} onOpen={(trigger) => openDocument(file, trigger)} />)}
              </div>}
            </div>
          </main>
        )}
      </div>

      {mode === 'select' && showSelectionFooter ? <div className="mt-3 flex shrink-0 flex-col gap-2 rounded-xl border border-border bg-card px-4 py-3 shadow-sm sm:flex-row sm:items-center sm:justify-between">
        <div className="flex min-w-0 flex-wrap gap-2">
          {selectedItems.slice(0, 4).map((item) => <span key={contextKey(item)} className="ce-badge max-w-48 truncate px-2.5 py-1 text-xs">{item.title}</span>)}
          {selectedItems.length > 4 ? <span className="ce-badge px-2.5 py-1 text-xs">+{selectedItems.length - 4} more</span> : null}
        </div>
        <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
          <button type="button" onClick={onCancel} className="ce-action min-h-10 px-4 text-sm">Cancel</button>
          <button type="button" onClick={() => onApplySelection?.(selectedItems)} disabled={selectedItems.length === 0} className="ce-action ce-action-primary min-h-10 px-4 text-sm disabled:opacity-50" data-testid="button-apply-context">Apply context</button>
        </div>
      </div> : null}
    </div>
  );
}
