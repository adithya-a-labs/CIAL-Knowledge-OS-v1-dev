import { useEffect, useMemo, useRef, useState } from 'react';
import type { InputHTMLAttributes } from 'react';
import { Link, useLocation } from 'wouter';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Activity, Bot, ChevronDown, ChevronRight, ChevronsUpDown, Clock3, File, FileText,
  Folder, FolderOpen, Grid2X2, HardDrive, List, MoreHorizontal, NotebookPen, PanelRightClose,
  PanelRightOpen, Pin, Plus, Search, Settings2, Upload,
} from 'lucide-react';
import { toast } from 'sonner';
import {
  createMyWorkspaceFolder, getMyWorkspaceFolder, getMyWorkspacePreferences, getMyWorkspaceSummary,
  getMyWorkspaceTree, resetMyWorkspacePreferences, saveMyWorkspacePreferences, uploadMyWorkspaceFiles,
} from '@/api/client';
import PrivacyBadge from '@/components/workspace/PrivacyBadge';
import WorkspaceCustomizeDrawer from '@/components/workspace/WorkspaceCustomizeDrawer';
import { Button } from '@/components/ui/button';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuSeparator, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Skeleton } from '@/components/ui/skeleton';
import { DEFAULT_WORKSPACE_PREFERENCES, normalizeWorkspacePreferences, WORKSPACE_WIDGET_REGISTRY } from '@/config/workspaceConfig';
import { MY_DOCUMENTS, RECENT_ACTIVITY } from '@/data/workspace/workspaceData';
import type { WorkspaceFile, WorkspaceFolderNode, WorkspacePreferences, WorkspaceTab, WorkspaceView, WorkspaceWidgetId } from '@/data/workspace/workspaceTypes';
import { cn } from '@/lib/utils';

const tabs: { id: WorkspaceTab; label: string }[] = [
  { id: 'overview', label: 'Overview' }, { id: 'files', label: 'Files' }, { id: 'notes', label: 'Notes' },
  { id: 'saved', label: 'Saved' }, { id: 'activity', label: 'Activity' },
];

const fallbackFolders: WorkspaceFolderNode[] = [
  { id: 'demo-chat', parent_id: null, name: 'Chat Uploads', system_key: 'chat_uploads', document_count: 2 },
  { id: 'demo-personal', parent_id: null, name: 'Personal Uploads', system_key: 'personal_uploads', document_count: MY_DOCUMENTS.length },
  { id: 'demo-projects', parent_id: null, name: 'Project Reports', system_key: null, document_count: 1 },
];

const fallbackFiles: WorkspaceFile[] = MY_DOCUMENTS.map((document, index) => ({
  id: document.id, folder_id: 'demo-personal', name: document.name, file_type: document.fileType,
  size_bytes: document.sizeBytes, modified_at: new Date(Date.now() - index * 86_400_000).toISOString(),
  status: index === 1 ? 'indexing' : 'indexed', indexed: index !== 1,
}));

function formatBytes(bytes: number) {
  if (!Number.isFinite(bytes)) return '—';
  if (bytes < 1024) return `${bytes} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let value = bytes / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && value >= 1024; index += 1) { value /= 1024; unit = units[index]; }
  return `${value.toFixed(value >= 10 ? 0 : 1)} ${unit}`;
}

function statusLabel(status: WorkspaceFile['status'], indexed: boolean) {
  if (indexed || status === 'indexed') return 'Indexed';
  return status[0].toUpperCase() + status.slice(1);
}

function StatusPill({ file }: { file: WorkspaceFile }) {
  const label = statusLabel(file.status, file.indexed);
  const tone = label === 'Indexed' ? 'bg-emerald-50 text-emerald-700' : label === 'Failed' || label === 'Unsupported' ? 'bg-rose-50 text-rose-700' : 'bg-amber-50 text-amber-700';
  return <span className={cn('inline-flex rounded-full px-2 py-1 text-[11px] font-semibold', tone)}>{label}</span>;
}

function FolderRail({ folders, activeId, onSelect, onNew }: { folders: WorkspaceFolderNode[]; activeId: string | null; onSelect: (id: string | null) => void; onNew: () => void }) {
  return (
    <aside className="hidden min-h-[34rem] w-56 shrink-0 border-r border-slate-200 bg-[#fbfcfa] p-3 lg:block">
      <p className="px-2 pb-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-500">Folders</p>
      <button onClick={() => onSelect(null)} className={cn('flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm font-semibold', activeId === null ? 'bg-[#eaf3e5] text-primary' : 'text-slate-800 hover:bg-slate-100')}>
        <FolderOpen size={16} /><span className="flex-1">My Workspace</span><ChevronDown size={14} />
      </button>
      <div className="mt-1 space-y-0.5 pl-2">
        {folders.filter((folder) => folder.parent_id === null).map((folder) => (
          <button key={folder.id} onClick={() => onSelect(folder.id)} className={cn('flex w-full items-center gap-2 rounded-lg px-2.5 py-2 text-left text-sm', activeId === folder.id ? 'bg-[#eaf3e5] font-semibold text-primary' : 'text-slate-700 hover:bg-slate-100')}>
            {folder.system_key ? <FolderOpen size={15} className="text-primary" /> : <Folder size={15} className="text-amber-500" />}
            <span className="min-w-0 flex-1 truncate">{folder.name}</span><span className="text-[10px] text-slate-400">{folder.document_count}</span>
          </button>
        ))}
      </div>
      <Button variant="ghost" className="mt-3 w-full justify-start text-primary" onClick={onNew}><Plus size={15} /> New Folder</Button>
    </aside>
  );
}

function FileBrowser({ files, folders, activeFolder, view, onView, onFolderSelect, density }: { files: WorkspaceFile[]; folders: WorkspaceFolderNode[]; activeFolder: string | null; view: WorkspaceView; onView: (view: WorkspaceView) => void; onFolderSelect: (id: string | null) => void; density: WorkspacePreferences['density'] }) {
  const [search, setSearch] = useState('');
  const [typeFilter, setTypeFilter] = useState('all');
  const [sort, setSort] = useState('modified_desc');
  const activeName = folders.find((folder) => folder.id === activeFolder)?.name;
  const visible = useMemo(() => {
    const result = files.filter((file) => file.name.toLowerCase().includes(search.toLowerCase()) && (typeFilter === 'all' || file.file_type === typeFilter));
    return result.sort((a, b) => sort === 'name_asc' ? a.name.localeCompare(b.name) : Date.parse(b.modified_at) - Date.parse(a.modified_at));
  }, [files, search, sort, typeFilter]);
  const rowPadding = density === 'compact' ? 'py-2' : density === 'spacious' ? 'py-4' : 'py-3';

  return (
    <section className="min-w-0 flex-1">
      <div className="border-b border-slate-200 px-4 py-3 sm:px-5">
        <div className="flex items-center gap-1 text-xs text-slate-500"><span>My Workspace</span>{activeName ? <><ChevronRight size={13} /><span className="font-medium text-slate-800">{activeName}</span></> : null}</div>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <select value={activeFolder ?? ''} onChange={(event) => onFolderSelect(event.target.value || null)} aria-label="Choose folder" className="h-9 w-full rounded-lg border border-slate-200 bg-white px-3 text-xs lg:hidden"><option value="">My Workspace</option>{folders.map((folder) => <option key={folder.id} value={folder.id}>{folder.name}</option>)}</select>
          <label className="relative min-w-[12rem] flex-1"><Search size={15} className="absolute left-3 top-2.5 text-slate-400" /><input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search this workspace" className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm outline-none focus:border-primary" /></label>
          <select value={typeFilter} onChange={(event) => setTypeFilter(event.target.value)} aria-label="Filter file type" className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs"><option value="all">All types</option>{[...new Set(files.map((file) => file.file_type))].map((type) => <option value={type} key={type}>{type.toUpperCase()}</option>)}</select>
          <select value={sort} onChange={(event) => setSort(event.target.value)} aria-label="Sort files" className="h-9 rounded-lg border border-slate-200 bg-white px-3 text-xs"><option value="modified_desc">Recently modified</option><option value="name_asc">Name A–Z</option></select>
          <div className="flex rounded-lg border border-slate-200 bg-white p-0.5"><button onClick={() => onView('list')} aria-label="List view" className={cn('rounded-md p-1.5', view === 'list' && 'bg-slate-100 text-primary')}><List size={16} /></button><button onClick={() => onView('grid')} aria-label="Grid view" className={cn('rounded-md p-1.5', view === 'grid' && 'bg-slate-100 text-primary')}><Grid2X2 size={16} /></button></div>
        </div>
      </div>
      {visible.length === 0 ? <div className="flex min-h-72 flex-col items-center justify-center px-6 text-center"><FolderOpen size={34} className="text-slate-300" /><h3 className="mt-3 text-sm font-semibold text-slate-900">This folder is empty</h3><p className="mt-1 text-xs text-slate-500">Upload a file or create a folder to start organizing your knowledge.</p></div> : view === 'grid' ? (
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">{visible.map((file) => <article key={file.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><FileText size={24} className="text-primary" /><Link href={`/knowledge/document/${file.id}`} className="mt-3 block truncate text-sm font-semibold text-slate-900 hover:text-primary">{file.name}</Link><div className="mt-3 flex items-center justify-between"><StatusPill file={file} /><span className="text-xs text-slate-500">{formatBytes(file.size_bytes)}</span></div></article>)}</div>
      ) : (
        <div className="overflow-x-auto"><table className="w-full min-w-[720px] text-left"><thead><tr className="border-b border-slate-200 bg-slate-50/70 text-[11px] uppercase tracking-wide text-slate-500"><th className="px-5 py-2.5 font-semibold">Name</th><th className="px-3 font-semibold">Type</th><th className="px-3 font-semibold">Status</th><th className="px-3 font-semibold">Modified</th><th className="px-3 font-semibold">Size</th><th className="px-3 font-semibold">Actions</th></tr></thead><tbody>{visible.map((file) => <tr key={file.id} className="border-b border-slate-100 hover:bg-[#fafcf9]"><td className={cn('px-5', rowPadding)}><div className="flex items-center gap-3"><FileText size={18} className="shrink-0 text-primary" /><Link href={`/knowledge/document/${file.id}`} className="max-w-sm truncate text-sm font-semibold text-slate-900 hover:text-primary">{file.name}</Link></div></td><td className="px-3 text-xs uppercase text-slate-500">{file.file_type}</td><td className="px-3"><StatusPill file={file} /></td><td className="px-3 text-xs text-slate-500">{new Date(file.modified_at).toLocaleDateString()}</td><td className="px-3 text-xs text-slate-500">{formatBytes(file.size_bytes)}</td><td className="px-3"><DropdownMenu><DropdownMenuTrigger asChild><Button variant="ghost" size="icon" aria-label={`Actions for ${file.name}`}><MoreHorizontal size={16} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem asChild><Link href={`/knowledge/document/${file.id}`}>Open</Link></DropdownMenuItem><DropdownMenuItem asChild><Link href={`/knowledge/document/${file.id}`}>Preview</Link></DropdownMenuItem><DropdownMenuItem asChild><Link href={`/assistant?context=${file.id}`}>Ask AI</Link></DropdownMenuItem><DropdownMenuItem>Pin</DropdownMenuItem><DropdownMenuSeparator /><DropdownMenuItem>Rename</DropdownMenuItem><DropdownMenuItem>Move</DropdownMenuItem><DropdownMenuItem>Download</DropdownMenuItem><DropdownMenuItem className="text-rose-600">Delete</DropdownMenuItem></DropdownMenuContent></DropdownMenu></td></tr>)}</tbody></table></div>
      )}
    </section>
  );
}

export default function WorkspacePage() {
  const [location] = useLocation();
  const queryClient = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);
  const treeQuery = useQuery({ queryKey: ['my-workspace-tree'], queryFn: getMyWorkspaceTree, retry: false });
  const summaryQuery = useQuery({ queryKey: ['my-workspace-summary'], queryFn: getMyWorkspaceSummary, retry: false });
  const preferencesQuery = useQuery({ queryKey: ['my-workspace-preferences'], queryFn: getMyWorkspacePreferences, retry: false });
  const fallback = treeQuery.isError || preferencesQuery.isError;
  const [activeFolder, setActiveFolder] = useState<string | null>(null);
  const folderQuery = useQuery({ queryKey: ['my-workspace-folder', activeFolder], queryFn: () => getMyWorkspaceFolder(activeFolder), retry: false, enabled: !fallback });
  const [preferences, setPreferences] = useState(DEFAULT_WORKSPACE_PREFERENCES);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>('files');
  const [view, setView] = useState<WorkspaceView>('list');
  const [customizeOpen, setCustomizeOpen] = useState(false);
  useEffect(() => { const next = normalizeWorkspacePreferences(preferencesQuery.data); setPreferences(next); setActiveTab(next.defaultTab); setView(next.defaultView); }, [preferencesQuery.data]);
  useEffect(() => {
    if (!preferencesQuery.isError) return;
    try {
      const saved = localStorage.getItem('cial-workspace-preferences-fallback');
      if (!saved) return;
      const next = normalizeWorkspacePreferences(JSON.parse(saved) as Partial<WorkspacePreferences>);
      setPreferences(next); setActiveTab(next.defaultTab); setView(next.defaultView);
    } catch {
      localStorage.removeItem('cial-workspace-preferences-fallback');
    }
  }, [preferencesQuery.isError]);
  useEffect(() => {
    if (location === '/saved-knowledge' || location === '/workspace/bookmarks') setActiveTab('saved');
  }, [location]);

  const folders = treeQuery.data?.folders ?? fallbackFolders;
  const files = fallback ? fallbackFiles.filter((file) => activeFolder === null || file.folder_id === activeFolder) : (folderQuery.data?.documents ?? []);
  const summary = summaryQuery.data;
  const saveMutation = useMutation({ mutationFn: (value: WorkspacePreferences) => fallback ? Promise.resolve(value) : saveMyWorkspacePreferences(value), onSuccess: (value) => { if (fallback) localStorage.setItem('cial-workspace-preferences-fallback', JSON.stringify(value)); queryClient.setQueryData(['my-workspace-preferences'], value); setCustomizeOpen(false); toast.success(fallback ? 'Saved locally in this browser' : 'Workspace preferences saved'); }, onError: () => toast.error('Could not save workspace preferences') });
  const resetMutation = useMutation({ mutationFn: () => fallback ? Promise.resolve(DEFAULT_WORKSPACE_PREFERENCES) : resetMyWorkspacePreferences(), onSuccess: (value) => { const next = normalizeWorkspacePreferences(value); setPreferences(next); toast.success('Organization defaults restored'); } });
  const uploadMutation = useMutation({ mutationFn: (filesToUpload: File[]) => uploadMyWorkspaceFiles(filesToUpload, activeFolder), onSuccess: () => { void Promise.all([queryClient.invalidateQueries({ queryKey: ['my-workspace-tree'] }), queryClient.invalidateQueries({ queryKey: ['my-workspace-folder'] }), queryClient.invalidateQueries({ queryKey: ['my-workspace-summary'] })]); toast.success('Upload queued for indexing'); }, onError: (error) => toast.error(error instanceof Error ? error.message : 'Upload failed') });
  const newFolder = async () => { const name = window.prompt('Folder name'); if (!name?.trim()) return; try { await createMyWorkspaceFolder(name.trim(), activeFolder); await queryClient.invalidateQueries({ queryKey: ['my-workspace-tree'] }); toast.success('Folder created'); } catch (error) { toast.error(error instanceof Error ? error.message : 'Could not create folder'); } };
  const handleFiles = (list: FileList | null) => { if (list?.length) uploadMutation.mutate([...list]); };

  return (
    <div className="mx-auto flex w-full max-w-[96rem] flex-col gap-5" data-testid="workspace-page">
      <header className="flex flex-col gap-4 pl-10 lg:pl-0 xl:flex-row xl:items-end xl:justify-between">
        <div><div className="flex items-center gap-2"><h1 className="text-3xl font-semibold tracking-tight text-slate-950">My Workspace</h1><PrivacyBadge size="sm" /></div><p className="mt-2 text-sm text-slate-600">Your private documents, notes, pins, uploads, and AI work.</p></div>
        <div className="flex flex-wrap items-center gap-2">
          <label className="relative order-last w-full sm:order-first sm:w-64"><Search size={15} className="absolute left-3 top-2.5 text-slate-400" /><input placeholder="Search workspace" className="h-9 w-full rounded-lg border border-slate-200 bg-white pl-9 pr-3 text-sm" /></label>
          <DropdownMenu><DropdownMenuTrigger asChild><Button variant="outline"><Plus size={15} />New<ChevronDown size={14} /></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => fileInput.current?.click()}><Upload />Upload files</DropdownMenuItem><DropdownMenuItem onSelect={() => folderInput.current?.click()}><FolderOpen />Upload folder</DropdownMenuItem><DropdownMenuItem onSelect={() => void newFolder()}><Folder />Create folder</DropdownMenuItem><DropdownMenuItem onSelect={() => setActiveTab('notes')}><NotebookPen />Create note</DropdownMenuItem></DropdownMenuContent></DropdownMenu>
          <Button onClick={() => fileInput.current?.click()} disabled={uploadMutation.isPending}><Upload size={15} />{uploadMutation.isPending ? 'Uploading…' : 'Upload'}</Button>
          <Button variant="outline" onClick={() => setCustomizeOpen(true)}><Settings2 size={15} />Customize</Button>
          <input ref={fileInput} type="file" multiple className="hidden" onChange={(event) => handleFiles(event.target.files)} />
          <input ref={folderInput} type="file" multiple className="hidden" {...({ webkitdirectory: '', directory: '' } as InputHTMLAttributes<HTMLInputElement>)} onChange={(event) => handleFiles(event.target.files)} />
        </div>
      </header>
      {fallback ? <div className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800" role="status">Workspace API unavailable — showing labelled local preview data. Uploads and server preferences are disabled until the API reconnects.</div> : null}
      <nav className="flex gap-1 overflow-x-auto border-b border-slate-200" aria-label="Workspace sections">{tabs.map((tab) => <button key={tab.id} onClick={() => setActiveTab(tab.id)} className={cn('border-b-2 px-4 py-2.5 text-sm font-medium', activeTab === tab.id ? 'border-primary text-primary' : 'border-transparent text-slate-500 hover:text-slate-900')}>{tab.label}</button>)}</nav>
      {treeQuery.isLoading || preferencesQuery.isLoading ? <div className="grid gap-3"><Skeleton className="h-12" /><Skeleton className="h-96" /></div> : activeTab === 'files' || activeTab === 'overview' ? (
        <>
          <div className={cn('grid min-w-0 gap-5', preferences.rightRailVisible && !preferences.rightRailCollapsed ? 'xl:grid-cols-[minmax(0,1fr)_18rem]' : 'grid-cols-1')}>
            <div className="flex min-w-0 overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_8px_28px_rgba(15,23,42,0.05)]"><FolderRail folders={folders} activeId={activeFolder} onSelect={setActiveFolder} onNew={() => void newFolder()} /><FileBrowser files={files} folders={folders} activeFolder={activeFolder} view={view} onView={setView} onFolderSelect={setActiveFolder} density={preferences.density} /></div>
            {preferences.rightRailVisible ? <aside className={cn('space-y-4', preferences.rightRailCollapsed && 'hidden')}><div className="hidden justify-end xl:flex"><Button variant="ghost" size="sm" onClick={() => setPreferences((current) => ({ ...current, rightRailCollapsed: true }))}><PanelRightClose size={15} />Collapse</Button></div>{preferences.widgetOrder.filter((id) => preferences.visibleWidgets.includes(id)).map((id) => <section key={id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm"><h2 className="flex items-center gap-2 text-sm font-semibold text-slate-950">{id === 'storage_usage' ? <HardDrive size={15} className="text-primary" /> : id === 'pinned_items' ? <Pin size={15} className="text-primary" /> : <Clock3 size={15} className="text-primary" />}{WORKSPACE_WIDGET_REGISTRY[id].label}</h2>{id === 'storage_usage' ? <div className="mt-3"><p className="text-sm text-slate-700">{summary?.storage.available === false ? 'Usage unavailable' : summary?.storage.quota_bytes ? `${formatBytes(summary.storage.used_bytes)} of ${formatBytes(summary.storage.quota_bytes)}` : `${formatBytes(summary?.storage.used_bytes ?? 0)} used · No quota`}</p>{summary?.storage.quota_bytes ? <div className="mt-2 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-primary" style={{ width: `${Math.min(100, (summary.storage.used_bytes / summary.storage.quota_bytes) * 100)}%` }} /></div> : null}</div> : id === 'pinned_items' ? <div className="mt-3 space-y-2">{summary?.pinned.length ? summary.pinned.map((item) => <Link key={item.id} href={`/knowledge/document/${item.id}`} className="block truncate text-xs text-slate-700 hover:text-primary">{item.name}</Link>) : <p className="text-xs text-slate-500">Pin files for quick access.</p>}</div> : <div className="mt-3 space-y-2">{(summary?.recent_activity ?? RECENT_ACTIVITY).slice(0, preferences.recentItemLimit).map((item) => <p key={item.id} className="text-xs leading-5 text-slate-600">{'action' in item ? item.action.replaceAll('.', ' ') : item.description}</p>)}</div>}</section>)}</aside> : null}
            {preferences.rightRailVisible && preferences.rightRailCollapsed ? <Button variant="outline" className="fixed bottom-6 right-6 z-20 shadow-lg" onClick={() => setPreferences((current) => ({ ...current, rightRailCollapsed: false }))}><PanelRightOpen size={15} />Widgets</Button> : null}
          </div>
          <div className="grid gap-5 lg:grid-cols-2"><section className="rounded-xl border border-slate-200 bg-white p-4"><div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><NotebookPen size={16} className="text-primary" />My Notes</h2><button onClick={() => setActiveTab('notes')} className="text-xs font-semibold text-primary">View all</button></div>{['PAPI alignment observation', 'Vendor call notes', 'AGL controller reset checklist'].map((note) => <button key={note} className="flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-sm hover:bg-slate-50"><File size={14} className="text-primary" />{note}</button>)}</section><section className="rounded-xl border border-slate-200 bg-white p-4"><div className="mb-3 flex items-center justify-between"><h2 className="flex items-center gap-2 text-sm font-semibold"><Bot size={16} className="text-primary" />Recent AI Conversations</h2><Link href="/assistant" className="text-xs font-semibold text-primary">Open AI</Link></div>{(summary?.recent_conversations ?? []).slice(0, preferences.recentItemLimit).map((conversation) => <Link href="/assistant" key={conversation.id} className="flex items-center gap-2 rounded-lg px-2 py-2 text-sm hover:bg-slate-50"><ChevronsUpDown size={14} className="text-primary" /><span className="truncate">{conversation.title}</span></Link>)}</section></div>
        </>
      ) : <section className="rounded-2xl border border-slate-200 bg-white p-8 text-center"><Activity size={28} className="mx-auto text-primary" /><h2 className="mt-3 text-lg font-semibold">{tabs.find((tab) => tab.id === activeTab)?.label}</h2><p className="mt-1 text-sm text-slate-500">This view uses the same private workspace boundary. Rich editing is deferred; Files is fully integrated.</p></section>}
      <WorkspaceCustomizeDrawer open={customizeOpen} value={preferences} saving={saveMutation.isPending} fallback={fallback} onOpenChange={setCustomizeOpen} onChange={setPreferences} onSave={() => saveMutation.mutate(preferences)} onReset={() => resetMutation.mutate()} />
    </div>
  );
}
