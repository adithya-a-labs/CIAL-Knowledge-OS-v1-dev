import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Bookmark, FileText, Info, Sparkles, StickyNote } from 'lucide-react';
import { listMyNotes } from '@/api/client';
import type { CorpusDocument, DocumentPreview } from '@/api/types';
import AIComposer from '@/components/assistant/AIComposer';
import DocumentAnalysisCard from '@/components/knowledge-center/DocumentAnalysisCard';
import { cn } from '@/lib/utils';

type Tab='ai'|'notes'|'bookmarks'|'metadata'|'related';

export default function DocumentAssistantPanel({document,preview,onAsk,onCitation}:{document:CorpusDocument;preview:DocumentPreview|null;onAsk:(question?:string)=>Promise<void>;onCitation:(page:number,chunkId?:string|null)=>void}){
  const[tab,setTab]=useState<Tab>('ai');const[question,setQuestion]=useState('');const[asking,setAsking]=useState(false);
  const notes=useQuery({queryKey:['document-linked-notes',document.id],queryFn:()=>listMyNotes({}),enabled:tab==='notes',retry:false});
  const linked=useMemo(()=>notes.data?.items.filter((note)=>note.linked_documents.some((item)=>item.id===document.id))??[],[document.id,notes.data]);
  const tabs:[Tab,string,typeof Sparkles][]=[['ai','AI',Sparkles],['notes','Notes',StickyNote],['bookmarks','Bookmarks',Bookmark],['metadata','Metadata',Info],['related','Related',FileText]];
  const submit=async()=>{if(!question.trim()||asking)return;setAsking(true);try{await onAsk(question.trim());}finally{setAsking(false)}};
  return <div className="flex h-full min-h-0 flex-col bg-white">
    <header className="flex h-12 items-center gap-2 border-b border-slate-200 px-4"><Sparkles size={16} className="text-primary"/><strong className="text-sm">AI Assistant</strong></header>
    <div className="flex overflow-x-auto border-b border-slate-200 px-2">{tabs.map(([value,label,Icon])=><button key={value} onClick={()=>setTab(value)} className={cn('flex h-10 items-center gap-1.5 border-b-2 px-2 text-xs',tab===value?'border-primary font-semibold text-primary':'border-transparent text-slate-600')}><Icon size={13}/>{label}</button>)}</div>
    <div className="min-h-0 flex-1 overflow-y-auto p-3">
      {tab==='ai'?<DocumentAnalysisCard document={document} onAsk={onAsk} onCitation={onCitation} onSuggestedQuestion={setQuestion}/>:null}
      {tab==='notes'?(notes.isLoading?<p className="text-sm text-slate-500">Loading linked notes…</p>:linked.length?<div className="space-y-2">{linked.map((note)=><a key={note.id} href={`/workspace/notes?note=${note.id}`} className="block rounded-lg border border-slate-200 p-3"><strong className="text-sm">{note.title}</strong><p className="mt-1 line-clamp-2 text-xs text-slate-500">{note.plain_text||'Empty note'}</p></a>)}</div>:<p className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">No notes are linked to this document.</p>):null}
      {tab==='bookmarks'?<p className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">Persisted document bookmarks are unavailable because no bookmark API is configured.</p>:null}
      {tab==='metadata'?<dl className="space-y-3 text-sm">{[['Type',document.file_type.toUpperCase()],['Size',`${Math.round(document.size_bytes/1024)} KB`],['Pages',document.page_count??preview?.page_count??'Unknown'],['Modified',document.modified_at?new Date(document.modified_at).toLocaleString():'Unknown'],['Indexing',document.indexing_status],['Repository path',document.relative_path]].map(([label,value])=><div key={String(label)}><dt className="text-xs text-slate-500">{label}</dt><dd className="mt-1 break-words font-medium">{String(value)}</dd></div>)}</dl>:null}
      {tab==='related'?<p className="rounded-lg border border-dashed border-slate-200 p-4 text-sm text-slate-500">No authorized document relationships are available.</p>:null}
    </div>
    {tab==='ai'?<div className="sticky bottom-0 border-t border-slate-200 bg-white p-3"><AIComposer value={question} onChange={setQuestion} onSubmit={submit} placeholder="Ask about this document…" disabled={asking} testId="document-ai-composer"/></div>:null}
  </div>;
}
