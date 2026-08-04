import { useCallback, useMemo, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { ArrowLeft, ChevronRight, FileText, Folder, Loader2, NotebookPen, Search, Upload } from 'lucide-react';
import {
  attachNotebookSources,
  getMyWorkspaceFolder,
  listMyNotes,
  uploadMyWorkspaceFiles,
} from '@/api/client';
import type { CorpusDocument, SelectedContextItem } from '@/api/types';
import type { ChatSource } from '@/types/assistant';
import CorpusExplorer, { type CorpusSelectionSummary } from '@/components/corpus/CorpusExplorer';
import DocumentViewerPanel from '@/components/assistant/DocumentViewerPanel';
import { Button } from '@/components/ui/button';
import { Checkbox } from '@/components/ui/checkbox';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { toast } from '@/hooks/use-toast';

type PickerTab = 'workspace' | 'knowledge' | 'upload' | 'notes';
type SelectionValue = { source_type: 'document' | 'note'; document_id?: string; note_id?: string; title: string };

const EMPTY_CORPUS_SUMMARY: CorpusSelectionSummary = {
  selectedEntities: 0,
  selectedDocuments: 0,
  selectedFolders: 0,
  resolvedDocuments: [],
  newDocuments: [],
  alreadyAttachedCount: 0,
  unavailableCount: 0,
};

function toViewerSource(value: { id: string; title: string; fileType?: string | null; mimeType?: string | null; origin?: string }): ChatSource {
  return {
    id: `notebook-preview-${value.id}`,
    citationIndex: 1,
    documentId: value.id,
    documentTitle: value.title,
    sourceType: value.origin === 'my_workspace' ? 'workspace' : 'enterprise',
    fileType: value.fileType ?? undefined,
    mimeType: value.mimeType ?? undefined,
  };
}

export default function NotebookSourcePicker({
  notebookId,
  open,
  attachedIds,
  onOpenChange,
}: {
  notebookId: string;
  open: boolean;
  attachedIds: ReadonlySet<string>;
  onOpenChange: (open: boolean) => void;
}) {
  const client = useQueryClient();
  const fileInput = useRef<HTMLInputElement>(null);
  const previewTrigger = useRef<HTMLElement | null>(null);
  const [tab, setTab] = useState<PickerTab>('workspace');
  const [folderId, setFolderId] = useState<string | null>(null);
  const [query, setQuery] = useState('');
  const [selected, setSelected] = useState(new Map<string, SelectionValue>());
  const [corpusSelectedItems, setCorpusSelectedItems] = useState<SelectedContextItem[]>([]);
  const [corpusSummary, setCorpusSummary] = useState<CorpusSelectionSummary>(EMPTY_CORPUS_SUMMARY);
  const [preview, setPreview] = useState<ChatSource | null>(null);

  const workspace = useQuery({
    queryKey: ['notebook-source-picker', 'workspace', folderId],
    queryFn: () => getMyWorkspaceFolder(folderId),
    enabled: open && tab === 'workspace',
    retry: false,
  });
  const notes = useQuery({
    queryKey: ['notebook-source-picker', 'notes', query],
    queryFn: () => listMyNotes({ query }),
    enabled: open && tab === 'notes',
    retry: false,
  });

  const reset = useCallback(() => {
    setSelected(new Map());
    setCorpusSelectedItems([]);
    setCorpusSummary(EMPTY_CORPUS_SUMMARY);
    setPreview(null);
    setQuery('');
  }, []);

  const closePreview = useCallback(() => {
    const documentId = preview?.documentId;
    setPreview(null);
    window.setTimeout(() => {
      const freshTrigger = documentId
        ? document.querySelector<HTMLElement>(`[data-source-preview-id="${documentId}"]`)
        : null;
      (freshTrigger ?? previewTrigger.current)?.focus();
    }, 0);
  }, [preview?.documentId]);

  const openCorpusPreview = useCallback((document: CorpusDocument, trigger: HTMLElement) => {
    previewTrigger.current = trigger;
    setPreview(toViewerSource({
      id: document.id,
      title: document.name,
      fileType: document.file_type,
      mimeType: document.mime_type,
      origin: 'knowledge_center',
    }));
  }, []);

  const attachmentPayload = useMemo(() => {
    const values = new Map<string, { source_type: 'document' | 'note'; document_id?: string; note_id?: string; is_default_active: boolean }>();
    for (const item of selected.values()) {
      const key = item.source_type === 'document' ? `document:${item.document_id}` : `note:${item.note_id}`;
      values.set(key, { source_type: item.source_type, document_id: item.document_id, note_id: item.note_id, is_default_active: true });
    }
    for (const document of corpusSummary.newDocuments) {
      values.set(`document:${document.id}`, { source_type: 'document', document_id: document.id, is_default_active: true });
    }
    return Array.from(values.values());
  }, [corpusSummary.newDocuments, selected]);

  const attach = useMutation({
    mutationFn: () => attachNotebookSources(notebookId, attachmentPayload),
    onSuccess: () => {
      void Promise.all([
        client.invalidateQueries({ queryKey: ['notebookSources', notebookId] }),
        client.invalidateQueries({ queryKey: ['notebookDetail', notebookId] }),
        client.invalidateQueries({ queryKey: ['notebookChatBinding', notebookId] }),
      ]);
      reset();
      onOpenChange(false);
      toast({ title: 'Sources attached' });
    },
    onError: (error) => toast({ title: 'Sources could not be attached', description: error instanceof Error ? error.message : undefined, variant: 'destructive' }),
  });

  const upload = useMutation({
    mutationFn: async (files: File[]) => uploadMyWorkspaceFiles(files),
    onSuccess: async (documents) => {
      await attachNotebookSources(notebookId, documents.map((document) => ({ source_type: 'document' as const, document_id: document.id, is_default_active: false })));
      await Promise.all([
        client.invalidateQueries({ queryKey: ['notebookSources', notebookId] }),
        client.invalidateQueries({ queryKey: ['notebookDetail', notebookId] }),
      ]);
      reset();
      toast({ title: 'Upload queued', description: 'The new source is attached while the standalone indexer works in the background.' });
      onOpenChange(false);
    },
    onError: (error) => toast({ title: 'Upload could not be queued', description: error instanceof Error ? error.message : undefined, variant: 'destructive' }),
  });

  const toggle = (item: { id: string; title: string; type: 'document' | 'note' }) => setSelected((current) => {
    const next = new Map(current);
    const key = `${item.type}:${item.id}`;
    if (next.has(key)) next.delete(key);
    else next.set(key, item.type === 'document'
      ? { source_type: 'document', document_id: item.id, title: item.title }
      : { source_type: 'note', note_id: item.id, title: item.title });
    return next;
  });

  const row = (item: { id: string; title: string; subtitle: string; type: 'document' | 'note'; fileType?: string | null; mimeType?: string | null; origin?: string; ready?: boolean }) => {
    const key = `${item.type}:${item.id}`;
    const checked = selected.has(key);
    const attached = attachedIds.has(item.id);
    return (
      <div key={key} className="flex items-center gap-3 border-b border-border px-3 py-3 last:border-0">
        <Checkbox checked={checked || attached} disabled={attached} onCheckedChange={() => toggle(item)} aria-label={`Select ${item.title}`} />
        <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary">{item.type === 'note' ? <NotebookPen size={17} /> : <FileText size={17} />}</span>
        <button data-source-preview-id={item.id} className="min-w-0 flex-1 text-left" onClick={(event) => {
          if (item.type === 'document') {
            previewTrigger.current = event.currentTarget;
            setPreview(toViewerSource({ id: item.id, title: item.title, fileType: item.fileType, mimeType: item.mimeType, origin: item.origin }));
          } else toggle(item);
        }}>
          <strong className="block truncate text-sm">{item.title}</strong>
          <span className="block truncate text-xs text-muted-foreground">{attached ? 'Already attached' : item.subtitle}</span>
        </button>
        {item.ready === false ? <span className="rounded-full bg-warning/10 px-2 py-1 text-[10px] text-warning-foreground">Indexing</span> : null}
      </div>
    );
  };

  const selectedCount = selected.size + corpusSelectedItems.length;

  return (
    <Dialog open={open} onOpenChange={(next) => { if (!next) reset(); onOpenChange(next); }}>
      <DialogContent className="flex h-dvh w-screen max-w-none flex-col gap-0 overflow-hidden rounded-none p-0 sm:h-[88vh] sm:w-[90vw] sm:max-w-[96rem] sm:rounded-2xl" data-testid="notebook-source-picker">
        <DialogHeader className="shrink-0 border-b border-border px-5 py-4 pr-14">
          <DialogTitle>Add sources</DialogTitle>
          <DialogDescription>{selectedCount} selected · references are attached without copying source files.</DialogDescription>
        </DialogHeader>

        <Tabs value={tab} onValueChange={(value) => { setTab(value as PickerTab); setQuery(''); setPreview(null); }} className="flex min-h-0 flex-1 flex-col overflow-hidden">
          <div className="shrink-0 overflow-x-auto border-b border-border px-4 py-2">
            <TabsList className="w-max">
              <TabsTrigger value="workspace">My Workspace</TabsTrigger>
              <TabsTrigger value="knowledge">Knowledge Center</TabsTrigger>
              <TabsTrigger value="upload">Upload</TabsTrigger>
              <TabsTrigger value="notes">Notes</TabsTrigger>
            </TabsList>
          </div>

          {preview ? <div className="flex min-h-0 flex-1 flex-col">
            <Button variant="ghost" className="m-2 shrink-0 self-start" onClick={closePreview}><ArrowLeft />Back to sources</Button>
            <div className="min-h-0 flex-1"><DocumentViewerPanel source={preview} sources={[preview]} onClose={closePreview} onSelectSource={setPreview} /></div>
          </div> : <>
            {tab === 'workspace' || tab === 'notes' ? <div className="shrink-0 border-b border-border p-3">
              <label className="relative block"><Search size={15} className="absolute left-3 top-2.5 text-muted-foreground" /><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder={`Search ${tab === 'notes' ? 'notes' : 'My Workspace'}`} className="pl-9" /></label>
            </div> : null}

            <TabsContent value="workspace" className="m-0 min-h-0 flex-1 overflow-y-auto">
              <button className="flex w-full items-center gap-2 border-b border-border px-4 py-3 text-sm font-medium text-primary" onClick={() => setFolderId(null)}><Folder size={16} />My Workspace</button>
              {workspace.isLoading ? <p className="p-5 text-sm text-muted-foreground">Loading workspace…</p> : workspace.isError ? <p className="p-5 text-sm text-destructive">Workspace sources are unavailable.</p> : <>
                {workspace.data?.folders.map((folder) => <button key={folder.id} onClick={() => setFolderId(folder.id)} className="flex w-full items-center gap-3 border-b border-border px-4 py-3 text-left text-sm hover:bg-muted"><Folder size={17} className="text-primary" /><span className="flex-1">{folder.name}</span><ChevronRight size={15} /></button>)}
                {workspace.data?.documents.filter((item) => item.name.toLowerCase().includes(query.toLowerCase())).map((item) => row({ id: item.id, title: item.name, subtitle: `${item.file_type.toUpperCase()} · ${item.status}`, type: 'document', fileType: item.file_type, origin: 'my_workspace', ready: item.indexed }))}
              </>}
            </TabsContent>

            <TabsContent value="knowledge" className="m-0 min-h-0 flex-1 overflow-hidden">
              <CorpusExplorer mode="select" embedded selectedItems={corpusSelectedItems} onSelectionChange={setCorpusSelectedItems}
                onSelectionSummaryChange={setCorpusSummary} onOpenDocument={openCorpusPreview} attachedDocumentIds={attachedIds} showSelectionFooter={false} />
            </TabsContent>

            <TabsContent value="upload" className="m-0 flex min-h-0 flex-1 flex-col items-center justify-center p-8 text-center">
              <input ref={fileInput} type="file" multiple className="hidden" accept=".pdf,.docx,.pptx,.xlsx,.csv,.txt,image/*" onChange={(event) => event.target.files?.length ? upload.mutate(Array.from(event.target.files)) : undefined} />
              <span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><Upload size={24} /></span>
              <h3 className="mt-4 font-semibold">Upload to My Workspace</h3>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">Files enter the existing governed personal upload flow and appear here immediately while background indexing continues.</p>
              <Button className="mt-5" onClick={() => fileInput.current?.click()} disabled={upload.isPending}>{upload.isPending ? <Loader2 className="animate-spin" /> : <Upload />}{upload.isPending ? 'Uploading…' : 'Choose files'}</Button>
            </TabsContent>

            <TabsContent value="notes" className="m-0 min-h-0 flex-1 overflow-y-auto">
              {notes.isLoading ? <p className="p-5 text-sm text-muted-foreground">Loading notes…</p> : notes.isError ? <p className="p-5 text-sm text-destructive">Notes are unavailable.</p> : notes.data?.items.map((item) => row({ id: item.id, title: item.title, subtitle: `Revision ${item.revision} · AI index ${item.indexing_status}`, type: 'note', ready: item.indexing_status === 'indexed' }))}
            </TabsContent>
          </>}
        </Tabs>

        <DialogFooter className="shrink-0 border-t border-border bg-card px-4 pt-3 pb-[calc(0.75rem+env(safe-area-inset-bottom))] sm:items-center sm:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-x-3 gap-y-1 text-xs text-muted-foreground" aria-live="polite">
            <span><strong className="text-foreground">{selectedCount}</strong> selected</span>
            {tab === 'knowledge' ? <>
              <span><strong className="text-foreground">{corpusSummary.resolvedDocuments.length}</strong> resolved documents</span>
              <span>{corpusSummary.alreadyAttachedCount} already attached</span>
              <span>{corpusSummary.unavailableCount} unavailable</span>
            </> : null}
          </div>
          <div className="flex shrink-0 gap-2">
            <Button variant="outline" onClick={() => { reset(); onOpenChange(false); }}>Cancel</Button>
            <Button disabled={attachmentPayload.length === 0 || attach.isPending || Boolean(preview)} onClick={() => attach.mutate()}>{attach.isPending ? 'Attaching…' : `Attach ${attachmentPayload.length || ''} source${attachmentPayload.length === 1 ? '' : 's'}`}</Button>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
