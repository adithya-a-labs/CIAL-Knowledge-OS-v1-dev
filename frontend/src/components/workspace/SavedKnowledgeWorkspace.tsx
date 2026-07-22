import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Bookmark, FileText, Trash2 } from 'lucide-react';
import { Link } from 'wouter';
import { listSavedKnowledge, removeSavedKnowledge } from '@/api/client';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

export default function SavedKnowledgeWorkspace(){
  const client=useQueryClient();const items=useQuery({queryKey:['saved-knowledge'],queryFn:listSavedKnowledge,retry:false});
  const remove=async(id:string)=>{try{await removeSavedKnowledge(id);await client.invalidateQueries({queryKey:['saved-knowledge']});toast.success('Removed from Saved Knowledge');}catch{toast.error('Saved item could not be removed');}};
  return <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white" data-testid="saved-knowledge-workspace"><header className="border-b border-slate-200 px-5 py-4"><h2 className="flex items-center gap-2 font-semibold"><Bookmark size={17} className="text-primary"/>Saved Knowledge</h2><p className="mt-1 text-xs text-slate-500">Private references to immutable AI summaries.</p></header>{items.isLoading?<p className="p-6 text-sm text-slate-500">Loading saved knowledge…</p>:items.isError?<p className="p-6 text-sm text-red-700">Saved Knowledge could not be loaded.</p>:items.data?.items.length?<div>{items.data.items.map((item)=><article key={item.id} className="flex flex-wrap items-center gap-3 border-b border-slate-100 px-5 py-4"><FileText size={17} className="text-primary"/><div className="min-w-0 flex-1"><h3 className="truncate text-sm font-semibold">{item.title}</h3><p className="mt-1 text-xs text-slate-500">Summary · {item.source_count} sources · {new Date(item.created_at).toLocaleString()}</p></div><Button variant="outline" size="sm" asChild><Link href={`/workspace/summaries/${item.summary_id}`}>Open</Link></Button><Button variant="ghost" size="icon" aria-label={`Remove ${item.title}`} onClick={()=>void remove(item.id)}><Trash2 size={15}/></Button></article>)}</div>:<div className="p-10 text-center"><Bookmark size={28} className="mx-auto text-slate-300"/><h3 className="mt-3 font-semibold">Nothing saved yet</h3><p className="mt-1 text-sm text-slate-500">Save a completed summary to keep it here.</p></div>}</section>;
}
