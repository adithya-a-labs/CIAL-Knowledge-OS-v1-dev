import { useMemo, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { BookOpenText, Clock3, FileStack, MoreHorizontal, Plus, Search, Trash2 } from 'lucide-react';
import { Link, useLocation } from 'wouter';
import { createNotebook, deleteNotebook, listNotebooks, updateNotebook } from '@/api/client';
import type { NotebookRecord } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from '@/components/ui/dropdown-menu';
import { Input } from '@/components/ui/input';
import { toast } from '@/hooks/use-toast';

function NotebookEditor({ open, item, onOpenChange }: { open: boolean; item?: NotebookRecord | null; onOpenChange: (open: boolean) => void }) {
  const queryClient = useQueryClient();
  const [, navigate] = useLocation();
  const [title, setTitle] = useState(item?.title ?? '');
  const [description, setDescription] = useState(item?.description ?? '');
  const mutation = useMutation({
    mutationFn: () => item ? updateNotebook(item.id, { title: title.trim(), description: description.trim() || null }) : createNotebook({ title: title.trim(), description: description.trim() || null }),
    onSuccess: (record) => {
      void queryClient.invalidateQueries({ queryKey: ['notebooks'] });
      onOpenChange(false);
      toast({ title: item ? 'Notebook updated' : 'Notebook created' });
      if (!item) navigate(`/notebooks/${record.id}`);
    },
    onError: (error) => toast({ title: 'Notebook could not be saved', description: error instanceof Error ? error.message : undefined, variant: 'destructive' }),
  });
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent data-testid="notebook-editor-dialog"><DialogHeader><DialogTitle>{item ? 'Rename notebook' : 'Create a notebook'}</DialogTitle><DialogDescription>Notebooks keep authorized sources, one existing assistant conversation, notes, and grounded outputs together.</DialogDescription></DialogHeader><label className="space-y-2 text-sm font-medium">Name<Input autoFocus value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Notebook name" maxLength={255} data-testid="notebook-title-input" /></label><label className="space-y-2 text-sm font-medium">Description <span className="font-normal text-muted-foreground">(optional)</span><textarea value={description} onChange={(event) => setDescription(event.target.value)} className="min-h-24 w-full resize-y rounded-lg border border-input bg-background px-3 py-2 text-sm outline-none focus-visible:ring-2 focus-visible:ring-ring" maxLength={2000} /></label><DialogFooter><Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button><Button disabled={!title.trim() || mutation.isPending} onClick={() => mutation.mutate()} data-testid="save-notebook">{mutation.isPending ? 'Saving…' : item ? 'Save' : 'Create notebook'}</Button></DialogFooter></DialogContent></Dialog>;
}

export default function NotebooksPage() {
  const queryClient = useQueryClient();
  const [query, setQuery] = useState('');
  const [editor, setEditor] = useState<{ open: boolean; item?: NotebookRecord | null }>({ open: false });
  const notebooks = useQuery({ queryKey: ['notebooks'], queryFn: ({ signal }) => listNotebooks(signal), retry: false });
  const remove = useMutation({ mutationFn: deleteNotebook, onSuccess: () => { void queryClient.invalidateQueries({ queryKey: ['notebooks'] }); toast({ title: 'Notebook moved to trash' }); }, onError: (error) => toast({ title: 'Notebook could not be deleted', description: error instanceof Error ? error.message : undefined, variant: 'destructive' }) });
  const filtered = useMemo(() => (notebooks.data?.items ?? []).filter((item) => `${item.title} ${item.description ?? ''}`.toLowerCase().includes(query.trim().toLowerCase())), [notebooks.data?.items, query]);
  return <div className="mx-auto flex w-full max-w-[86rem] flex-col gap-6" data-testid="notebook-library">
    <header className="flex flex-wrap items-end justify-between gap-4 border-b border-border pb-5"><div><p className="text-xs font-semibold uppercase tracking-[0.14em] text-primary">Evidence workspaces</p><h1 className="mt-2 text-3xl font-semibold tracking-tight">Notebooks</h1><p className="mt-2 max-w-2xl text-sm text-muted-foreground">Build persistent, source-aware workspaces around the CIAL Assistant.</p></div><Button onClick={() => setEditor({ open: true })} data-testid="new-notebook"><Plus />New notebook</Button></header>
    <div className="flex flex-wrap items-center gap-3"><label className="relative min-w-[16rem] max-w-xl flex-1"><Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground"/><Input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search notebooks" className="pl-9" /></label><span className="rounded-full border border-border bg-card px-3 py-1.5 text-xs text-muted-foreground">My Workspace</span></div>
    {notebooks.isLoading ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3" role="status">{[0,1,2].map((item) => <div key={item} className="h-44 animate-pulse rounded-xl border border-border bg-card" />)}</div> : notebooks.isError ? <section className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center"><h2 className="font-semibold">Notebooks are temporarily unavailable</h2><p className="mt-2 text-sm text-muted-foreground">{notebooks.error instanceof Error ? notebooks.error.message : 'Try again.'}</p><Button className="mt-4" variant="outline" onClick={() => void notebooks.refetch()}>Retry</Button></section> : filtered.length ? <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">{filtered.map((item) => <article key={item.id} className="group relative min-h-44 rounded-xl border border-border bg-card p-5 shadow-sm transition hover:border-primary/35 hover:shadow-md"><Link href={`/notebooks/${item.id}`} className="absolute inset-0 rounded-xl" aria-label={`Open ${item.title}`} /><div className="relative pointer-events-none flex items-start gap-3"><span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-primary/10 text-primary"><BookOpenText size={19}/></span><div className="min-w-0 flex-1"><h2 className="truncate font-semibold">{item.title}</h2><p className="mt-1 line-clamp-2 text-sm text-muted-foreground">{item.description || 'A private evidence-aware notebook.'}</p></div></div><div className="relative pointer-events-none mt-6 flex flex-wrap gap-3 text-xs text-muted-foreground"><span className="inline-flex items-center gap-1"><FileStack size={13}/>{item.source_count} sources</span><span>{item.active_source_count} active</span><span>{item.artifact_count} outputs</span><span className="ml-auto inline-flex items-center gap-1"><Clock3 size={13}/>{new Date(item.last_activity_at).toLocaleDateString()}</span></div><DropdownMenu><DropdownMenuTrigger asChild><Button className="absolute right-3 top-3 z-10 opacity-0 group-hover:opacity-100 focus:opacity-100" variant="ghost" size="icon" aria-label={`Notebook actions for ${item.title}`}><MoreHorizontal/></Button></DropdownMenuTrigger><DropdownMenuContent align="end"><DropdownMenuItem onSelect={() => setEditor({ open: true, item })}>Rename</DropdownMenuItem><DropdownMenuItem className="text-destructive" onSelect={() => remove.mutate(item.id)}><Trash2/>Delete</DropdownMenuItem></DropdownMenuContent></DropdownMenu></article>)}</div> : <section className="flex min-h-80 flex-col items-center justify-center rounded-2xl border border-dashed border-border bg-card/40 p-8 text-center"><span className="flex h-14 w-14 items-center justify-center rounded-2xl bg-primary/10 text-primary"><BookOpenText size={26}/></span><h2 className="mt-4 text-lg font-semibold">{query ? 'No notebooks match your search' : 'Create your first notebook'}</h2><p className="mt-2 max-w-md text-sm text-muted-foreground">Attach existing CIAL sources, use the grounded assistant, capture notes, and generate supported outputs without copying documents.</p>{!query ? <Button className="mt-5" onClick={() => setEditor({ open: true })}><Plus/>New notebook</Button> : null}</section>}
    {editor.open ? <NotebookEditor key={editor.item?.id ?? 'new'} open={editor.open} item={editor.item} onOpenChange={(open) => setEditor((current) => ({ ...current, open }))} /> : null}
  </div>;
}
