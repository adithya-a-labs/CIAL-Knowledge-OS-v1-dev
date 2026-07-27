import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Lock, NotebookPen, Pin, Search } from 'lucide-react';
import CorpusExplorer from '@/components/corpus/CorpusExplorer';
import { listMyNotes } from '@/api/client';
import type { SelectedContextItem } from '@/api/types';

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
  const [tab,setTab]=useState<'knowledge'|'notes'>('knowledge');
  const [query,setQuery]=useState('');
  const notes=useQuery({queryKey:['context-notes',query],queryFn:()=>listMyNotes({query}),enabled:open&&tab==='notes',retry:false});

  useEffect(() => {
    if (open) setDraftItems(selectedItems);
  }, [open, selectedItems]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/45 p-3" data-testid="context-manager-dialog">
      <div className="flex h-[min(92dvh,56rem)] w-full max-w-6xl flex-col overflow-hidden rounded-xl border border-popover-border bg-popover p-4 text-popover-foreground shadow-2xl">
        <div className="mb-3 flex gap-1 border-b border-border"><button onClick={()=>setTab('knowledge')} className={`px-3 py-2 text-sm ${tab==='knowledge'?'border-b-2 border-primary font-semibold text-primary':'text-muted-foreground'}`}>Knowledge</button><button onClick={()=>setTab('notes')} className={`px-3 py-2 text-sm ${tab==='notes'?'border-b-2 border-primary font-semibold text-primary':'text-muted-foreground'}`}>Private Notes</button></div>
        {tab==='knowledge'?<CorpusExplorer
          mode="select"
          selectedItems={draftItems}
          onSelectionChange={setDraftItems}
          onApplySelection={(items) => {
            onApply(items);
            onClose();
          }}
          onCancel={onClose}
        />:<div className="flex min-h-0 flex-1 flex-col"><label className="relative mb-3 block"><Search size={15} className="absolute left-3 top-2.5 text-muted-foreground"/><input value={query} onChange={(event)=>setQuery(event.target.value)} placeholder="Search private notes" className="h-9 w-full rounded-lg border border-border pl-9 pr-3 text-sm"/></label><div className="min-h-0 flex-1 overflow-y-auto">{notes.isLoading?<p className="p-4 text-sm text-muted-foreground">Loading notes…</p>:notes.isError?<p className="p-4 text-sm text-destructive">Notes could not be loaded.</p>:notes.data?.items.map((note)=>{const selected=draftItems.some((item)=>item.type==='note'&&item.id===note.id);return <button key={note.id} onClick={()=>setDraftItems((current)=>selected?current.filter((item)=>!(item.type==='note'&&item.id===note.id)):[...current,{id:note.id,type:'note',title:note.title,relative_path:`notes/${note.id}`,updated_at:note.updated_at,is_pinned:note.is_pinned}])} className={`flex w-full items-center gap-3 border-b border-border px-3 py-3 text-left hover:bg-muted ${selected?'bg-accent':''}`}><NotebookPen size={16} className="text-primary"/><span className="min-w-0 flex-1"><strong className="block truncate text-sm">{note.title}</strong><span className="mt-1 flex items-center gap-2 text-xs text-muted-foreground"><Lock size={11}/>Private · {new Date(note.updated_at).toLocaleString()}</span></span>{note.is_pinned?<Pin size={14} className="text-primary"/>:null}<span className={`h-4 w-4 rounded border ${selected?'border-primary bg-primary':''}`}/></button>})}</div><div className="mt-3 flex justify-end gap-2"><button onClick={onClose} className="rounded-lg border px-4 py-2 text-sm">Cancel</button><button onClick={()=>{onApply(draftItems);onClose();}} className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white">Use selected context</button></div></div>}
      </div>
    </div>
  );
}
