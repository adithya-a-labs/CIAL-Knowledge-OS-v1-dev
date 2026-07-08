import { useMemo, useState } from 'react';
import {
  Bot,
  CheckSquare,
  ChevronDown,
  ChevronRight,
  Download,
  FileText,
  Folder,
  FolderPlus,
  Grid3X3,
  Info,
  List,
  Menu,
  MoreVertical,
  MoveRight,
  PanelLeftOpen,
  Search,
  Share2,
  Sparkles,
  Star,
  Trash2,
  Upload,
  X,
} from 'lucide-react';
import { cn } from '@/lib/utils';
import {
  driveFiles,
  driveFolders,
  driveNavItems,
  driveSortOptions,
  driveTreeNodes,
  filterDriveFiles,
  filterDriveFolders,
  getBreadcrumb,
  getChildFolders,
  getFolderById,
  sortDriveFiles,
  type DriveFile,
  type DriveFolder,
  type DrivePreviewType,
  type DriveSortMode,
  type DriveTreeNode,
  type DriveViewMode,
} from '@/data/knowledgeDriveData';

interface KnowledgeDriveSidebarProps {
  activeFolderId: string | null;
  expandedTreeNodes: string[];
  onToggleTreeNode: (id: string) => void;
  onSelectFolder: (folderId: string | null) => void;
  onNewFolder: () => void;
  onUpload: () => void;
}

interface KnowledgeDriveSearchProps {
  searchQuery: string;
  onSearchChange: (value: string) => void;
  onUpload: () => void;
  onNewFolder: () => void;
  onOpenInAssistant: () => void;
}

interface SuggestedFoldersProps {
  folders: DriveFolder[];
  activeFolderId: string | null;
  onOpenFolder: (folder: DriveFolder) => void;
}

interface SuggestedFilesProps {
  files: DriveFile[];
  viewMode: DriveViewMode;
  sortMode: DriveSortMode;
  selectedItems: string[];
  onViewModeChange: (mode: DriveViewMode) => void;
  onSortModeChange: (mode: DriveSortMode) => void;
  onViewMore: () => void;
  onOpenFile: (file: DriveFile) => void;
  onToggleItem: (id: string) => void;
  onAction: (action: string, file: DriveFile) => void;
}

interface FullFileBrowserProps {
  folders: DriveFolder[];
  files: DriveFile[];
  activeFolderId: string | null;
  viewMode: DriveViewMode;
  sortMode: DriveSortMode;
  selectedItems: string[];
  onOpenFolder: (folder: DriveFolder) => void;
  onOpenFile: (file: DriveFile) => void;
  onToggleItem: (id: string) => void;
  onToggleAll: () => void;
  onViewModeChange: (mode: DriveViewMode) => void;
  onSortModeChange: (mode: DriveSortMode) => void;
  onAction: (action: string, file: DriveFile) => void;
  onBackHome: () => void;
}

function IconButton({
  children,
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex h-9 w-9 items-center justify-center rounded-lg text-slate-500 transition-colors hover:bg-slate-100 hover:text-slate-900 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function DriveButton({
  children,
  variant = 'secondary',
  className,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: 'primary' | 'secondary' | 'ghost' }) {
  return (
    <button
      type="button"
      className={cn(
        'inline-flex h-10 items-center justify-center gap-2 rounded-xl px-3 text-sm font-semibold transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
        variant === 'primary' && 'bg-primary text-white shadow-sm hover:bg-[#3d6834]',
        variant === 'secondary' && 'border border-slate-200 bg-white text-slate-700 shadow-sm hover:border-slate-300 hover:bg-slate-50',
        variant === 'ghost' && 'text-slate-600 hover:bg-slate-100 hover:text-slate-950',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

function KnowledgeDriveSearch({ searchQuery, onSearchChange, onUpload, onNewFolder, onOpenInAssistant }: KnowledgeDriveSearchProps) {
  return (
    <div className="grid gap-3 xl:grid-cols-[minmax(18rem,1fr)_auto]">
      <label className="relative block min-w-0">
        <span className="sr-only">Ask or search across Knowledge Center</span>
        <Search size={20} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
        <input
          type="search"
          value={searchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Ask or search across Knowledge Center..."
          className="h-12 w-full rounded-xl border border-slate-200 bg-white px-12 pr-20 text-sm font-medium text-slate-800 shadow-sm transition-colors placeholder:text-slate-500 hover:border-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/15"
        />
        <span className="absolute right-4 top-1/2 hidden -translate-y-1/2 text-xs font-semibold text-slate-500 sm:block">⌘K</span>
      </label>

      <div className="flex flex-wrap items-center gap-2">
        <DriveButton onClick={onOpenInAssistant} className="h-12">
          <Sparkles size={16} className="text-primary" />
          AI
          <ChevronDown size={15} />
        </DriveButton>
        <DriveButton onClick={onUpload} variant="primary">
          <Upload size={16} />
          Upload Document
        </DriveButton>
        <DriveButton onClick={onNewFolder}>
          <FolderPlus size={16} />
          New Folder
        </DriveButton>
        <IconButton aria-label="More Knowledge Center actions" className="border border-slate-200 bg-white shadow-sm">
          <MoreVertical size={17} />
        </IconButton>
      </div>
    </div>
  );
}

function KnowledgeDriveBanner({ onDismiss, onOpenInAssistant }: { onDismiss: () => void; onOpenInAssistant: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3 rounded-2xl border border-[#dcebd4] bg-[#f8fdf6] px-4 py-3 text-sm text-slate-700">
      <span className="flex min-w-0 items-center gap-3">
        <span className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-[#dcebd4] bg-white text-primary shadow-sm">
          <Sparkles size={17} />
        </span>
        <span className="min-w-0">
          <span className="block font-semibold text-slate-900">Ask AI across selected folders, SOPs, manuals and policies.</span>
          <span className="block text-xs text-slate-500">Use file actions like summarize, find related SOPs, or ask AI about this item.</span>
        </span>
      </span>
      <span className="flex flex-shrink-0 items-center gap-2">
        <DriveButton onClick={onOpenInAssistant} variant="secondary" className="hidden bg-white sm:inline-flex">
          <Sparkles size={15} />
          Use in AI Assistant
        </DriveButton>
        <IconButton onClick={onDismiss} aria-label="Dismiss AI helper banner" className="h-8 w-8">
          <X size={15} />
        </IconButton>
      </span>
    </div>
  );
}

function KnowledgeDriveSidebar({
  activeFolderId,
  expandedTreeNodes,
  onToggleTreeNode,
  onSelectFolder,
  onNewFolder,
  onUpload,
}: KnowledgeDriveSidebarProps) {
  return (
    <aside className="hidden max-h-[calc(100dvh-8rem)] min-h-[42rem] w-72 flex-shrink-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm xl:flex xl:flex-col">
      <div className="border-b border-slate-200 p-3">
        <DriveButton onClick={onUpload} variant="primary" className="h-11 w-full justify-start">
          <Upload size={17} />
          <span className="flex-1 text-left">New / Upload</span>
          <span className="h-5 border-l border-white/30" />
          <ChevronDown size={15} />
        </DriveButton>
        <DriveButton onClick={onNewFolder} variant="secondary" className="mt-2 h-10 w-full justify-start">
          <FolderPlus size={16} />
          New Folder
        </DriveButton>
      </div>

      <div className="scrollbar-soft flex-1 overflow-y-auto p-3">
        <button
          type="button"
          onClick={() => onSelectFolder(null)}
          className={cn(
            'mb-2 flex w-full items-center gap-2 rounded-xl px-3 py-2 text-left text-sm font-semibold transition-colors hover:bg-slate-100',
            activeFolderId === null ? 'bg-[#f0f7ed] text-primary' : 'text-slate-700',
          )}
        >
          <Folder size={17} />
          CIAL Drive
        </button>

        <div className="space-y-0.5">
          {driveNavItems.map((item) => {
            const Icon = item.icon;
            const active = item.folderId && activeFolderId === item.folderId;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onSelectFolder(item.folderId ?? null)}
                className={cn(
                  'flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm font-medium transition-colors hover:bg-slate-100',
                  active ? 'bg-[#f0f7ed] text-primary' : 'text-slate-600',
                )}
              >
                <Icon size={16} className="flex-shrink-0" />
                <span className="truncate">{item.label}</span>
              </button>
            );
          })}
        </div>

        <div className="mt-4 border-t border-slate-200 pt-3">
          <p className="mb-2 px-3 text-[11px] font-bold uppercase tracking-normal text-slate-500">Folder Tree</p>
          <KnowledgeDriveTree
            nodes={driveTreeNodes}
            activeFolderId={activeFolderId}
            expandedTreeNodes={expandedTreeNodes}
            onToggleTreeNode={onToggleTreeNode}
            onSelectFolder={onSelectFolder}
          />
        </div>
      </div>
    </aside>
  );
}

function KnowledgeDriveTree({
  nodes,
  activeFolderId,
  expandedTreeNodes,
  onToggleTreeNode,
  onSelectFolder,
  depth = 0,
}: {
  nodes: DriveTreeNode[];
  activeFolderId: string | null;
  expandedTreeNodes: string[];
  onToggleTreeNode: (id: string) => void;
  onSelectFolder: (folderId: string | null) => void;
  depth?: number;
}) {
  return (
    <div className="space-y-0.5">
      {nodes.map((node) => {
        const Icon = node.icon ?? Folder;
        const expanded = expandedTreeNodes.includes(node.id);
        const active = Boolean(node.folderId && node.folderId === activeFolderId);
        const hasChildren = Boolean(node.children?.length);

        return (
          <div key={node.id}>
            <button
              type="button"
              onClick={() => {
                if (hasChildren) onToggleTreeNode(node.id);
                if (node.folderId) onSelectFolder(node.folderId);
              }}
              className={cn(
                'flex w-full items-center gap-1.5 rounded-lg py-1.5 pr-2 text-left text-sm transition-colors hover:bg-slate-100',
                active ? 'bg-[#f0f7ed] font-semibold text-primary' : 'text-slate-600',
              )}
              style={{ paddingLeft: `${8 + depth * 14}px` }}
            >
              {hasChildren ? (
                <ChevronRight size={14} className={cn('flex-shrink-0 transition-transform', expanded && 'rotate-90')} />
              ) : (
                <span className="w-3.5 flex-shrink-0" />
              )}
              <Icon size={15} className="flex-shrink-0" />
              <span className="truncate">{node.label}</span>
            </button>
            {hasChildren && expanded && (
              <KnowledgeDriveTree
                nodes={node.children ?? []}
                activeFolderId={activeFolderId}
                expandedTreeNodes={expandedTreeNodes}
                onToggleTreeNode={onToggleTreeNode}
                onSelectFolder={onSelectFolder}
                depth={depth + 1}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

function Breadcrumb({ activeFolderId, onSelectFolder }: { activeFolderId: string | null; onSelectFolder: (folderId: string | null) => void }) {
  const crumbs = getBreadcrumb(activeFolderId);

  return (
    <nav aria-label="Knowledge Center location" className="flex flex-wrap items-center gap-1 text-sm text-slate-500">
      <button type="button" onClick={() => onSelectFolder(null)} className="font-medium text-slate-700 hover:text-primary">
        Knowledge Center
      </button>
      {crumbs.map((folder) => (
        <span key={folder.id} className="inline-flex items-center gap-1">
          <ChevronRight size={14} />
          <button type="button" onClick={() => onSelectFolder(folder.id)} className="font-medium text-slate-700 hover:text-primary">
            {folder.name}
          </button>
        </span>
      ))}
    </nav>
  );
}

function CurrentLocationHeader({
  activeFolderId,
  onSelectFolder,
}: {
  activeFolderId: string | null;
  onSelectFolder: (folderId: string | null) => void;
}) {
  const folder = getFolderById(activeFolderId);
  const title = folder ? getBreadcrumb(activeFolderId).map((item) => item.name).join(' / ') : 'Knowledge Center';
  const activeLabel = folder ? folder.name : 'All Content';

  return (
    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
      <div className="min-w-0">
        <div className="sr-only">
          <Breadcrumb activeFolderId={activeFolderId} onSelectFolder={onSelectFolder} />
        </div>
        <h1 className="text-xl font-semibold tracking-normal text-slate-950">{title}</h1>
        <button type="button" onClick={() => onSelectFolder(activeFolderId)} className="mt-1 inline-flex items-center gap-1 text-xs font-semibold text-primary">
          {activeLabel}
          <ChevronDown size={13} />
        </button>
      </div>
      <IconButton aria-label="Knowledge Center information" className="border border-slate-200 bg-white shadow-sm">
        <Info size={17} />
      </IconButton>
    </div>
  );
}

function SuggestedFolders({ folders, activeFolderId, onOpenFolder }: SuggestedFoldersProps) {
  return (
    <section>
      <div className="mb-3 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-slate-950">Suggested folders</h2>
        <button type="button" className="text-xs font-semibold text-primary hover:text-[#2f5626]">
          View all
        </button>
      </div>
      <div className="scrollbar-soft grid gap-3 sm:grid-cols-2 lg:grid-cols-3 2xl:grid-cols-4">
        {folders.map((folder) => (
          <FolderCard key={folder.id} folder={folder} active={activeFolderId === folder.id} onOpenFolder={onOpenFolder} />
        ))}
      </div>
    </section>
  );
}

function FolderCard({ folder, active, onOpenFolder }: { folder: DriveFolder; active: boolean; onOpenFolder: (folder: DriveFolder) => void }) {
  return (
    <button
      type="button"
      onClick={() => onOpenFolder(folder)}
      className={cn(
        'group flex min-h-20 items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:bg-slate-50 hover:shadow-md',
        active && 'border-primary/45 bg-[#f8fdf6] ring-2 ring-primary/15',
      )}
    >
      <span className="inline-flex h-11 w-11 flex-shrink-0 items-center justify-center rounded-xl bg-amber-50 text-amber-600">
        <Folder size={23} />
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-sm font-semibold text-slate-950">{folder.name}</span>
        <span className="mt-1 block truncate text-xs text-slate-500">{folder.locationLabel}</span>
      </span>
      <span
        role="button"
        tabIndex={-1}
        className="inline-flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg text-slate-400 opacity-100 transition-colors group-hover:bg-white group-hover:text-slate-700"
        aria-label={`More actions for ${folder.name}`}
      >
        <MoreVertical size={16} />
      </span>
    </button>
  );
}

function KnowledgeDriveToolbar({
  viewMode,
  sortMode,
  onViewModeChange,
  onSortModeChange,
}: {
  viewMode: DriveViewMode;
  sortMode: DriveSortMode;
  onViewModeChange: (mode: DriveViewMode) => void;
  onSortModeChange: (mode: DriveSortMode) => void;
}) {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <div className="inline-flex rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <IconButton
          aria-label="Grid view"
          onClick={() => onViewModeChange('grid')}
          className={cn('h-8 w-8', viewMode === 'grid' && 'bg-[#f0f7ed] text-primary')}
        >
          <Grid3X3 size={16} />
        </IconButton>
        <IconButton
          aria-label="List view"
          onClick={() => onViewModeChange('list')}
          className={cn('h-8 w-8', viewMode === 'list' && 'bg-[#f0f7ed] text-primary')}
        >
          <List size={16} />
        </IconButton>
      </div>
      <label className="relative">
        <span className="sr-only">Sort files</span>
        <select
          value={sortMode}
          onChange={(event) => onSortModeChange(event.target.value as DriveSortMode)}
          className="h-10 appearance-none rounded-xl border border-slate-200 bg-white px-3 pr-9 text-sm font-semibold text-slate-700 shadow-sm transition-colors hover:border-slate-300 focus:border-primary focus:ring-2 focus:ring-primary/15"
        >
          {driveSortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              Sort: {option.label}
            </option>
          ))}
        </select>
        <ChevronDown size={15} className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-slate-500" />
      </label>
    </div>
  );
}

function SuggestedFiles({
  files,
  viewMode,
  sortMode,
  selectedItems,
  onViewModeChange,
  onSortModeChange,
  onViewMore,
  onOpenFile,
  onToggleItem,
  onAction,
}: SuggestedFilesProps) {
  return (
    <section>
      <div className="mb-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <h2 className="text-base font-semibold text-slate-950">Suggested files</h2>
        <KnowledgeDriveToolbar viewMode={viewMode} sortMode={sortMode} onViewModeChange={onViewModeChange} onSortModeChange={onSortModeChange} />
      </div>

      {files.length === 0 ? (
        <EmptyState />
      ) : viewMode === 'grid' ? (
        <FileGridView files={files} selectedItems={selectedItems} onOpenFile={onOpenFile} onToggleItem={onToggleItem} onAction={onAction} />
      ) : (
        <FileListView
          files={files}
          selectedItems={selectedItems}
          onToggleItem={onToggleItem}
          onToggleAll={() => {}}
          onOpenFile={onOpenFile}
          onAction={onAction}
        />
      )}

      <div className="mt-5 flex justify-center">
        <DriveButton onClick={onViewMore}>
          View more
          <ChevronRight size={16} />
        </DriveButton>
      </div>
    </section>
  );
}

function FileGridView({
  files,
  selectedItems,
  onOpenFile,
  onToggleItem,
  onAction,
  compact = false,
}: {
  files: DriveFile[];
  selectedItems: string[];
  onOpenFile: (file: DriveFile) => void;
  onToggleItem: (id: string) => void;
  onAction: (action: string, file: DriveFile) => void;
  compact?: boolean;
}) {
  return (
    <div className={cn('grid gap-4 sm:grid-cols-2 lg:grid-cols-3', compact ? 'xl:grid-cols-4 2xl:grid-cols-5' : 'xl:grid-cols-4 2xl:grid-cols-6')}>
      {files.map((file) => (
        <FileCard key={file.id} file={file} selected={selectedItems.includes(file.id)} onOpenFile={onOpenFile} onToggleItem={onToggleItem} onAction={onAction} />
      ))}
    </div>
  );
}

function FileCard({
  file,
  selected,
  onOpenFile,
  onToggleItem,
  onAction,
}: {
  file: DriveFile;
  selected: boolean;
  onOpenFile: (file: DriveFile) => void;
  onToggleItem: (id: string) => void;
  onAction: (action: string, file: DriveFile) => void;
}) {
  return (
    <article
      className={cn(
        'group overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-all hover:-translate-y-0.5 hover:border-slate-300 hover:shadow-md',
        selected && 'border-primary/50 ring-2 ring-primary/15',
      )}
    >
      <div className="flex items-start gap-2 px-3 py-3">
        <FileIcon type={file.previewType} compact />
        <button type="button" onClick={() => onOpenFile(file)} className="min-w-0 flex-1 text-left">
          <h3 className="line-clamp-2 min-h-10 text-sm font-semibold leading-5 text-slate-900">{file.name}</h3>
        </button>
        <input
          type="checkbox"
          checked={selected}
          onChange={() => onToggleItem(file.id)}
          aria-label={`Select ${file.name}`}
          className="mt-1 h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/25"
        />
        <ActionMenu file={file} onAction={onAction} />
      </div>

      <button type="button" onClick={() => onOpenFile(file)} className="block w-full px-3">
        <FilePreviewThumbnail type={file.previewType} />
      </button>

      <div className="flex items-center gap-2 px-3 py-3">
        <span className="inline-flex h-7 w-7 flex-shrink-0 items-center justify-center rounded-full bg-primary text-[11px] font-bold text-white">
          {file.ownerInitials}
        </span>
        <p className="min-w-0 flex-1 truncate text-xs text-slate-500">{file.activityLabel}</p>
        <span className="flex-shrink-0 text-xs text-slate-500">{file.lastUpdated}</span>
      </div>
    </article>
  );
}

function FilePreviewThumbnail({ type }: { type: DrivePreviewType }) {
  if (type === 'xlsx') {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
        <div className="grid h-28 w-36 grid-cols-4 grid-rows-5 overflow-hidden rounded-lg border border-emerald-200 bg-white">
          {Array.from({ length: 20 }).map((_, index) => (
            <span key={index} className={cn('border-b border-r border-emerald-100', index < 4 && 'bg-emerald-50')} />
          ))}
        </div>
      </div>
    );
  }

  if (type === 'pptx') {
    return (
      <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-slate-200 bg-orange-50/50">
        <div className="h-28 w-40 rounded-lg border border-orange-200 bg-white p-3">
          <div className="h-4 w-24 rounded bg-orange-200" />
          <div className="mt-4 h-14 rounded bg-slate-100" />
          <div className="mt-3 h-2 w-28 rounded bg-orange-100" />
        </div>
      </div>
    );
  }

  return (
    <div className="flex aspect-[4/3] items-center justify-center rounded-xl border border-slate-200 bg-slate-50">
      <div className="h-32 w-24 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div className={cn('mb-3 h-3 w-14 rounded', type === 'pdf' || type === 'sop' || type === 'policy' ? 'bg-red-200' : 'bg-blue-200')} />
        <div className="space-y-2">
          <div className="h-2 rounded bg-slate-200" />
          <div className="h-2 rounded bg-slate-200" />
          <div className="h-2 w-16 rounded bg-slate-200" />
          <div className="mt-3 h-10 rounded bg-slate-100" />
        </div>
      </div>
    </div>
  );
}

function FileIcon({ type, compact = false }: { type: DrivePreviewType; compact?: boolean }) {
  const iconMap: Record<DrivePreviewType, { label: string; className: string; icon: React.ReactNode }> = {
    pdf: { label: 'PDF', className: 'bg-red-50 text-red-600', icon: <FileText size={compact ? 15 : 18} /> },
    docx: { label: 'DOC', className: 'bg-blue-50 text-blue-600', icon: <FileText size={compact ? 15 : 18} /> },
    xlsx: { label: 'XLS', className: 'bg-emerald-50 text-emerald-600', icon: <CheckSquare size={compact ? 15 : 18} /> },
    pptx: { label: 'PPT', className: 'bg-orange-50 text-orange-600', icon: <PanelLeftOpen size={compact ? 15 : 18} /> },
    image: { label: 'IMG', className: 'bg-violet-50 text-violet-600', icon: <FileText size={compact ? 15 : 18} /> },
    video: { label: 'VID', className: 'bg-pink-50 text-pink-600', icon: <FileText size={compact ? 15 : 18} /> },
    archive: { label: 'ZIP', className: 'bg-slate-100 text-slate-600', icon: <FileText size={compact ? 15 : 18} /> },
    policy: { label: 'POL', className: 'bg-red-50 text-red-600', icon: <ShieldMini /> },
    sop: { label: 'SOP', className: 'bg-amber-50 text-amber-700', icon: <CheckSquare size={compact ? 15 : 18} /> },
  };
  const item = iconMap[type];

  return (
    <span className={cn('inline-flex flex-shrink-0 items-center justify-center rounded-lg', compact ? 'h-8 w-8' : 'h-10 w-10', item.className)}>
      {item.icon}
      <span className="sr-only">{item.label}</span>
    </span>
  );
}

function ShieldMini() {
  return <FileText size={15} />;
}

function ActionMenu({ file, onAction }: { file: DriveFile; onAction: (action: string, file: DriveFile) => void }) {
  const actions = [
    ['open', 'Open'],
    ['summarize', 'Summarize'],
    ['ask-ai', 'Ask AI about this'],
    ['related', 'Find related SOPs'],
    ['share', 'Share'],
    ['download', 'Download'],
    ['move', 'Move'],
    ['rename', 'Rename'],
    ['delete', 'Delete'],
  ];

  return (
    <div className="relative flex-shrink-0">
      <IconButton aria-label={`Actions for ${file.name}`} className="h-8 w-8">
        <MoreVertical size={16} />
      </IconButton>
      <div className="absolute right-0 top-8 z-20 hidden w-44 rounded-xl border border-slate-200 bg-white p-1 text-xs shadow-lg group-hover:block group-focus-within:block">
        {actions.map(([key, label]) => (
          <button
            key={key}
            type="button"
            onClick={() => onAction(key, file)}
            className={cn('flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-slate-700 hover:bg-slate-50', key === 'delete' && 'text-red-600 hover:bg-red-50')}
          >
            {key === 'ask-ai' && <Bot size={13} />}
            {key === 'summarize' && <Sparkles size={13} />}
            {key === 'download' && <Download size={13} />}
            {key === 'share' && <Share2 size={13} />}
            {key === 'move' && <MoveRight size={13} />}
            {key === 'delete' && <Trash2 size={13} />}
            {!['ask-ai', 'summarize', 'download', 'share', 'move', 'delete'].includes(key) && <FileText size={13} />}
            {label}
          </button>
        ))}
      </div>
    </div>
  );
}

function FileListView({
  files,
  selectedItems,
  onToggleItem,
  onToggleAll,
  onOpenFile,
  onAction,
}: {
  files: DriveFile[];
  selectedItems: string[];
  onToggleItem: (id: string) => void;
  onToggleAll: () => void;
  onOpenFile: (file: DriveFile) => void;
  onAction: (action: string, file: DriveFile) => void;
}) {
  const allSelected = files.length > 0 && files.every((file) => selectedItems.includes(file.id));

  return (
    <div className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm">
      <div className="grid min-w-[64rem] grid-cols-[2.5rem_minmax(18rem,1fr)_9rem_9rem_8rem_7rem_9rem_3rem] items-center border-b border-slate-200 bg-slate-50/80 px-3 py-3 text-xs font-semibold text-slate-500">
        <input type="checkbox" checked={allSelected} onChange={onToggleAll} aria-label="Select all files" className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/25" />
        <span>Name</span>
        <span>Owner</span>
        <span>Department</span>
        <span>Type</span>
        <span>Size</span>
        <span>Last updated</span>
        <span className="text-right">Actions</span>
      </div>
      <div className="scrollbar-soft overflow-x-auto">
        {files.map((file) => (
          <div
            key={file.id}
            className={cn(
              'group grid min-w-[64rem] grid-cols-[2.5rem_minmax(18rem,1fr)_9rem_9rem_8rem_7rem_9rem_3rem] items-center border-b border-slate-100 px-3 py-2.5 text-sm last:border-b-0 hover:bg-slate-50',
              selectedItems.includes(file.id) && 'bg-[#f0f7ed]/80',
            )}
          >
            <input
              type="checkbox"
              checked={selectedItems.includes(file.id)}
              onChange={() => onToggleItem(file.id)}
              aria-label={`Select ${file.name}`}
              className="h-4 w-4 rounded border-slate-300 text-primary focus:ring-primary/25"
            />
            <button type="button" onClick={() => onOpenFile(file)} className="flex min-w-0 items-center gap-3 text-left">
              <FileIcon type={file.previewType} compact />
              <span className="truncate font-medium text-slate-800">{file.name}</span>
              {file.starred && <Star size={13} className="flex-shrink-0 text-amber-500" />}
            </button>
            <span className="truncate text-slate-600">{file.owner}</span>
            <span className="truncate text-slate-600">{file.department}</span>
            <span className="text-slate-600">{file.type}</span>
            <span className="text-slate-600">{file.size}</span>
            <span className="text-slate-600">{file.lastUpdated}</span>
            <ActionMenu file={file} onAction={onAction} />
          </div>
        ))}
      </div>
    </div>
  );
}

function FullFileBrowser({
  folders,
  files,
  activeFolderId,
  viewMode,
  sortMode,
  selectedItems,
  onOpenFolder,
  onOpenFile,
  onToggleItem,
  onToggleAll,
  onViewModeChange,
  onSortModeChange,
  onAction,
  onBackHome,
}: FullFileBrowserProps) {
  return (
    <section className="space-y-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-slate-950">All files</h2>
          <p className="mt-0.5 text-sm text-slate-500">Folders first, then trusted documents and SOPs.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <DriveButton onClick={onBackHome} variant="ghost">Suggested</DriveButton>
          <KnowledgeDriveToolbar viewMode={viewMode} sortMode={sortMode} onViewModeChange={onViewModeChange} onSortModeChange={onSortModeChange} />
        </div>
      </div>

      {folders.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
          {folders.map((folder) => (
            <FolderCard key={folder.id} folder={folder} active={activeFolderId === folder.id} onOpenFolder={onOpenFolder} />
          ))}
        </div>
      )}

      {files.length === 0 && folders.length === 0 ? (
        <EmptyState />
      ) : viewMode === 'grid' ? (
        <FileGridView files={files} selectedItems={selectedItems} onOpenFile={onOpenFile} onToggleItem={onToggleItem} onAction={onAction} compact />
      ) : (
        <FileListView files={files} selectedItems={selectedItems} onToggleItem={onToggleItem} onToggleAll={onToggleAll} onOpenFile={onOpenFile} onAction={onAction} />
      )}
    </section>
  );
}

function EmptyState() {
  return (
    <div className="flex min-h-56 flex-col items-center justify-center rounded-2xl border border-dashed border-slate-200 bg-white px-4 py-10 text-center">
      <Search size={24} className="text-slate-400" />
      <h3 className="mt-3 text-sm font-semibold text-slate-800">No files found</h3>
      <p className="mt-1 max-w-sm text-sm text-slate-500">Try a different search or choose another folder from the tree.</p>
    </div>
  );
}

export function KnowledgeCenterPage() {
  const [searchQuery, setSearchQuery] = useState('');
  const [activeFolderId, setActiveFolderId] = useState<string | null>(null);
  const [expandedTreeNodes, setExpandedTreeNodes] = useState<string[]>(['departments', 'engineering', 'operations', 'safety', 'it']);
  const [selectedItems, setSelectedItems] = useState<string[]>([]);
  const [viewMode, setViewMode] = useState<DriveViewMode>('grid');
  const [sortMode, setSortMode] = useState<DriveSortMode>('latest');
  const [fullBrowserOpen, setFullBrowserOpen] = useState(false);
  const [isAIBannerVisible, setIsAIBannerVisible] = useState(true);

  const activeFolder = getFolderById(activeFolderId);
  const hasSearch = searchQuery.trim().length > 0;

  const suggestedFolders = useMemo(() => {
    const base = driveFolders.filter((folder) => folder.suggested);
    return filterDriveFolders(base, searchQuery);
  }, [searchQuery]);

  const childFolders = useMemo(() => {
    return filterDriveFolders(getChildFolders(activeFolderId), searchQuery);
  }, [activeFolderId, searchQuery]);

  const visibleFiles = useMemo(() => {
    return sortDriveFiles(filterDriveFiles(driveFiles, searchQuery, activeFolderId), sortMode);
  }, [activeFolderId, searchQuery, sortMode]);

  const suggestedFiles = useMemo(() => visibleFiles.slice(0, 12), [visibleFiles]);

  const handleSelectFolder = (folderId: string | null) => {
    setActiveFolderId(folderId);
    setSelectedItems([]);
    if (folderId) setFullBrowserOpen(true);
  };

  const handleOpenFolder = (folder: DriveFolder) => {
    handleSelectFolder(folder.id);
  };

  const handleToggleTreeNode = (id: string) => {
    setExpandedTreeNodes((current) => (current.includes(id) ? current.filter((nodeId) => nodeId !== id) : [...current, id]));
  };

  const handleToggleItem = (id: string) => {
    setSelectedItems((current) => (current.includes(id) ? current.filter((itemId) => itemId !== id) : [...current, id]));
  };

  const handleToggleAll = () => {
    const visibleIds = visibleFiles.map((file) => file.id);
    const allSelected = visibleIds.length > 0 && visibleIds.every((id) => selectedItems.includes(id));
    setSelectedItems((current) => (allSelected ? current.filter((id) => !visibleIds.includes(id)) : [...new Set([...current, ...visibleIds])]));
  };

  const handleOpenFile = (_file: DriveFile) => {};
  const handleFileAction = (_action: string, _file: DriveFile) => {};
  const handleOpenInAssistant = () => {};
  const handleUpload = () => {};
  const handleNewFolder = () => {};

  const showFullBrowser = fullBrowserOpen || hasSearch;

  return (
    <div className="fluid-section" data-testid="knowledge-center-page">
      <KnowledgeDriveSearch
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onUpload={handleUpload}
        onNewFolder={handleNewFolder}
        onOpenInAssistant={handleOpenInAssistant}
      />

      <div className="mt-4 flex gap-5">
        <KnowledgeDriveSidebar
          activeFolderId={activeFolderId}
          expandedTreeNodes={expandedTreeNodes}
          onToggleTreeNode={handleToggleTreeNode}
          onSelectFolder={handleSelectFolder}
          onNewFolder={handleNewFolder}
          onUpload={handleUpload}
        />

        <main className="min-w-0 flex-1 space-y-5">
          <div className="xl:hidden">
            <DriveButton variant="secondary" className="mb-3">
              <Menu size={16} />
              Knowledge folders
            </DriveButton>
          </div>

          {isAIBannerVisible && (
            <KnowledgeDriveBanner onDismiss={() => setIsAIBannerVisible(false)} onOpenInAssistant={handleOpenInAssistant} />
          )}
          <CurrentLocationHeader activeFolderId={activeFolderId} onSelectFolder={handleSelectFolder} />

          {showFullBrowser ? (
            <FullFileBrowser
              folders={childFolders}
              files={visibleFiles}
              activeFolderId={activeFolderId}
              viewMode={viewMode}
              sortMode={sortMode}
              selectedItems={selectedItems}
              onOpenFolder={handleOpenFolder}
              onOpenFile={handleOpenFile}
              onToggleItem={handleToggleItem}
              onToggleAll={handleToggleAll}
              onViewModeChange={setViewMode}
              onSortModeChange={setSortMode}
              onAction={handleFileAction}
              onBackHome={() => {
                setFullBrowserOpen(false);
                setSearchQuery('');
                setActiveFolderId(null);
                setSelectedItems([]);
              }}
            />
          ) : (
            <>
              <SuggestedFolders folders={suggestedFolders} activeFolderId={activeFolderId} onOpenFolder={handleOpenFolder} />
              <SuggestedFiles
                files={suggestedFiles}
                viewMode={viewMode}
                sortMode={sortMode}
                selectedItems={selectedItems}
                onViewModeChange={setViewMode}
                onSortModeChange={setSortMode}
                onViewMore={() => setFullBrowserOpen(true)}
                onOpenFile={handleOpenFile}
                onToggleItem={handleToggleItem}
                onAction={handleFileAction}
              />
            </>
          )}

          {activeFolder && (
            <div className="sr-only" aria-live="polite">
              Current folder: {activeFolder.name}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}
