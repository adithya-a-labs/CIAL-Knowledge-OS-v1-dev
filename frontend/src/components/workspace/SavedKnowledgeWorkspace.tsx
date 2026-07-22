import { useMemo, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bookmark, Copy, FileText, NotebookPen, Search, Star, Trash2 } from 'lucide-react';
import { Link } from 'wouter';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import {
  convertSavedKnowledgeToNote,
  duplicateSavedKnowledge,
  listSavedKnowledge,
  removeSavedKnowledge,
  updateSavedKnowledge,
} from '@/api/client';
import type { SavedKnowledgeRecord } from '@/api/types';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { toast } from 'sonner';

function citationLink(citation: Record<string, unknown>) {
  const documentId = typeof citation.document_id === 'string' ? citation.document_id : null;
  const noteId = typeof citation.note_id === 'string' ? citation.note_id : null;
  const page = typeof citation.page === 'number'
    ? citation.page
    : typeof citation.page_number === 'number' ? citation.page_number : null;
  const blockId = typeof citation.block_id === 'string' ? citation.block_id : null;
  if (documentId) return `/knowledge/document/${documentId}${page ? `?page=${page}` : ''}`;
  if (noteId) {
    const params = new URLSearchParams({ note: noteId });
    if (blockId) params.set('citation', blockId);
    return `/workspace/notes?${params}`;
  }
  return null;
}

export default function SavedKnowledgeWorkspace() {
  const client = useQueryClient();
  const [query, setQuery] = useState('');
  const [favorites, setFavorites] = useState(false);
  const [active, setActive] = useState<SavedKnowledgeRecord | null>(null);
  const items = useQuery({
    queryKey: ['saved-knowledge', query, favorites],
    queryFn: () => listSavedKnowledge({ query, favorite: favorites }),
    retry: false,
  });
  const collections = useMemo(
    () => [...new Set(items.data?.items.map((item) => item.collection).filter((value): value is string => Boolean(value)))],
    [items.data],
  );
  const refresh = () => client.invalidateQueries({ queryKey: ['saved-knowledge'] });

  const remove = async (item: SavedKnowledgeRecord) => {
    if (!window.confirm(`Delete “${item.title}”?`)) return;
    try {
      await removeSavedKnowledge(item.id);
      setActive(null);
      await refresh();
      toast.success('Saved Knowledge deleted');
    } catch {
      toast.error('Saved item could not be deleted');
    }
  };

  const favorite = async (item: SavedKnowledgeRecord) => {
    try {
      const updated = await updateSavedKnowledge(item.id, {
        expected_version: item.version,
        is_favorite: !item.is_favorite,
      });
      setActive((current) => current?.id === updated.id ? updated : current);
      await refresh();
    } catch {
      toast.error('Favorite could not be updated');
    }
  };

  return (
    <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="saved-knowledge-workspace">
      <header className="border-b border-slate-200 px-5 py-4">
        <div className="flex flex-wrap items-center gap-3">
          <div className="min-w-0 flex-1">
            <h2 className="flex items-center gap-2 font-semibold"><Bookmark size={17} className="text-primary" />Saved Knowledge</h2>
            <p className="mt-1 text-xs text-slate-500">Private grounded answers and immutable summary assets with preserved provenance.</p>
          </div>
          <label className="relative">
            <Search size={14} className="absolute left-3 top-2.5 text-slate-400" />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search saved knowledge" className="h-9 w-64 rounded-lg border border-slate-200 pl-9 pr-3 text-sm" />
          </label>
          <button onClick={() => setFavorites((value) => !value)} className={`rounded-lg px-3 py-2 text-xs ${favorites ? 'bg-[#eaf3e5] font-semibold text-primary' : 'bg-slate-100 text-slate-600'}`}>
            <Star size={13} className="mr-1 inline" />Favorites
          </button>
        </div>
        {collections.length ? <div className="mt-3 flex gap-2 overflow-x-auto">{collections.map((value) => <span key={value} className="rounded-full bg-slate-100 px-3 py-1 text-xs">{value}</span>)}</div> : null}
      </header>

      {items.isLoading ? (
        <div className="grid gap-3 p-5 sm:grid-cols-2"><div className="h-32 animate-pulse rounded-xl bg-slate-100" /><div className="h-32 animate-pulse rounded-xl bg-slate-100" /></div>
      ) : items.isError ? (
        <p className="p-6 text-sm text-red-700">Saved Knowledge could not be loaded.</p>
      ) : items.data?.items.length ? (
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-3">
          {items.data.items.map((item) => (
            <article key={item.id} className="rounded-xl border border-slate-200 p-4 transition hover:border-[#bed1b7] hover:shadow-sm">
              <div className="flex items-start gap-3">
                <span className="rounded-lg bg-[#edf5e9] p-2 text-primary"><FileText size={17} /></span>
                <div className="min-w-0 flex-1"><h3 className="line-clamp-2 text-sm font-semibold">{item.title}</h3><p className="mt-1 text-xs text-slate-500">{item.item_type === 'answer' ? 'AI answer' : 'Summary'} · {item.source_count} sources · {new Date(item.created_at).toLocaleDateString()}</p></div>
                <button aria-label={item.is_favorite ? 'Remove favorite' : 'Add favorite'} onClick={() => void favorite(item)}><Star size={16} className={item.is_favorite ? 'fill-amber-400 text-amber-500' : 'text-slate-300'} /></button>
              </div>
              {item.description ? <p className="mt-3 line-clamp-2 text-xs leading-5 text-slate-600">{item.description}</p> : null}
              <div className="mt-3 flex flex-wrap gap-1">{item.tags.map((tag) => <span key={tag} className="rounded-full bg-slate-100 px-2 py-1 text-[10px]">{tag}</span>)}</div>
              <div className="mt-4 flex gap-2">
                <Button size="sm" variant="outline" onClick={() => setActive(item)}>Open</Button>
                <Button size="sm" variant="ghost" onClick={() => void convertSavedKnowledgeToNote(item.id).then((note) => { toast.success('Converted to note'); location.href = `/workspace/notes?note=${note.id}`; })}><NotebookPen size={14} />Note</Button>
                <Button size="sm" variant="ghost" onClick={() => void duplicateSavedKnowledge(item.id).then(refresh)} aria-label={`Duplicate ${item.title}`}><Copy size={14} /></Button>
                <Button size="sm" variant="ghost" onClick={() => void remove(item)} aria-label={`Delete ${item.title}`}><Trash2 size={14} /></Button>
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="p-10 text-center"><Bookmark size={28} className="mx-auto text-slate-300" /><h3 className="mt-3 font-semibold">Nothing saved yet</h3><p className="mt-1 text-sm text-slate-500">Use Save to Knowledge on a grounded AI answer or completed summary.</p></div>
      )}

      <Dialog open={Boolean(active)} onOpenChange={(open) => { if (!open) setActive(null); }}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
          <DialogHeader><DialogTitle>{active?.title}</DialogTitle><DialogDescription>{active?.item_type === 'answer' ? 'Saved grounded answer' : 'Saved summary'} · Version {active?.version}</DialogDescription></DialogHeader>
          {active ? (
            <article>
              <div className="mb-4 flex flex-wrap gap-2 text-xs text-slate-500">{active.collection ? <span>Collection: {active.collection}</span> : null}<span>{active.source_count} sources</span><span>{new Date(active.updated_at).toLocaleString()}</span></div>
              {active.original_question ? <div className="mb-4 rounded-lg bg-[#f5f8f3] p-3 text-sm"><strong>Original question</strong><p className="mt-1">{active.original_question}</p></div> : null}
              <div className="prose prose-slate max-w-none"><ReactMarkdown remarkPlugins={[remarkGfm]}>{active.body_markdown}</ReactMarkdown></div>
              <section className="mt-6 border-t border-slate-200 pt-4">
                <h3 className="font-semibold">Sources and citations</h3>
                {active.citations.length ? (
                  <div className="mt-2 space-y-2">
                    {active.citations.map((citation, index) => {
                      const href = citationLink(citation);
                      const available = citation.availability === 'available';
                      const snippet = typeof citation.snippet === 'string' ? citation.snippet : null;
                      return available && href ? (
                        <Link key={index} href={href} className="block rounded-lg border border-slate-200 p-3 text-sm hover:bg-slate-50">
                          <span className="font-medium">Source {index + 1}</span>
                          {typeof citation.page === 'number' ? <span className="ml-2 text-xs text-slate-500">Page {citation.page}</span> : null}
                          {snippet ? <span className="mt-1 line-clamp-2 block text-xs text-slate-500">{snippet}</span> : null}
                        </Link>
                      ) : <div key={index} className="rounded-lg border border-slate-200 p-3 text-sm text-slate-500">Source {index + 1} is unavailable or access was revoked.</div>;
                    })}
                  </div>
                ) : <p className="mt-2 text-sm text-slate-500">No citation snapshot was saved.</p>}
              </section>
            </article>
          ) : null}
        </DialogContent>
      </Dialog>
    </section>
  );
}
