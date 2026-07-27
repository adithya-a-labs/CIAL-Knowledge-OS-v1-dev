import { useEffect, useRef, useState } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { AlertTriangle, BookmarkPlus, ChevronDown, Clock3, FileSearch, LoaderCircle, MessageSquareText, RefreshCw, Sparkles, X } from 'lucide-react';
import {
  askSummaryFollowUp,
  createDocumentAnalysis,
  getDocumentAnalysis,
  saveSummaryToSavedKnowledge,
  type AnalysisProgress as AnalysisProgressValue,
  type DocumentAnalysisLength,
  type DocumentAnalysisPayload,
  type DocumentAnalysisType,
  type GroundedAnalysisItem,
  type SummaryRecord,
} from '@/api/client';
import type { CorpusDocument } from '@/api/types';
import { cn } from '@/lib/utils';
import { assistantConversationPath } from '@/lib/assistantNavigation';

const TERMINAL=new Set(['completed','failed','cancelled','stale']);
export function analysisPollInterval(startedAt:number,hidden:boolean,status?:string){
  if(!status||TERMINAL.has(status))return false;
  if(hidden)return 20_000;
  const elapsed=Date.now()-startedAt;
  if(elapsed<30_000)return 2_000;
  if(elapsed<120_000)return 4_000;
  return 9_000;
}

export function AnalysisVersionBadge({summary}:{summary:SummaryRecord}){
  return <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-muted-foreground"><span className="rounded-full bg-muted px-2 py-1">{summary.summary_length}</span>{summary.document_version_number?<span>Version {summary.document_version_number}</span>:null}{summary.completed_at?<span className="inline-flex items-center gap-1"><Clock3 size={11}/>{new Date(summary.completed_at).toLocaleString()}</span>:null}{summary.stale||summary.status==='stale'?<span className="rounded-full bg-warning/15 px-2 py-1 font-medium text-warning-foreground">Stale</span>:null}</div>;
}

export function AnalysisProgress({progress}:{progress?:AnalysisProgressValue}){
  const completed=progress?.completed??0;const total=progress?.total??0;const percent=total?Math.min(100,Math.round(completed/total*100)):12;
  const detail=progress?.stage==='mapping'&&progress.map_total?`Reading sections ${Math.min((progress.map_completed??0)+1,progress.map_total)}/${progress.map_total}`:progress?.stage==='reducing'&&progress.reduce_total_groups?`Consolidating findings—level ${progress.reduce_level??1} group ${progress.reduce_group??1}/${progress.reduce_total_groups}`:progress?.message;
  return <section className="rounded-xl border border-primary/20 bg-primary/5 p-4" aria-live="polite" data-testid="analysis-progress"><div className="flex items-center gap-2 text-sm font-semibold text-foreground"><LoaderCircle size={16} className="text-primary motion-safe:animate-spin"/>Preparing document analysis…</div><p className="mt-2 text-xs text-muted-foreground">{detail||'Loading the authorized document version'}</p><div className="mt-3 h-1.5 overflow-hidden rounded-full bg-muted" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}><div className="h-full rounded-full bg-primary transition-[width] motion-reduce:transition-none" style={{width:`${percent}%`}}/></div></section>;
}

function ItemList({items}:{items:GroundedAnalysisItem[]}){return <ul className="mt-2 space-y-2">{items.map((item,index)=><li key={`${item.text}-${index}`} className="text-xs leading-5 text-foreground"><span>{item.text}</span> <span className="whitespace-nowrap font-medium text-primary">{item.citation_ids.map((id)=>`[${id}]`).join(' ')}</span></li>)}</ul>}

export function AnalysisSections({payload}:{payload:DocumentAnalysisPayload}){
  const collections:Array<[string,GroundedAnalysisItem[]]>=[['Overview',payload.overview??[]],['Key Findings',payload.key_findings],['Important Dates',payload.important_dates],['Requirements',payload.requirements],['Action Items',payload.action_items]];
  return <div className="space-y-3" data-testid="analysis-sections">{payload.sections.filter((section)=>section.items.length).map((section)=><section key={section.heading} className="rounded-xl border border-border p-3"><h3 className="text-sm font-semibold text-foreground">{section.heading}</h3><ItemList items={section.items}/></section>)}{collections.filter(([,items])=>items.length).map(([heading,items])=><section key={heading} className="rounded-xl border border-border p-3"><h3 className="text-sm font-semibold text-foreground">{heading}</h3><ItemList items={items}/></section>)}{payload.coverage_gaps.length?<section className="rounded-xl border border-warning/30 bg-warning/10 p-3"><h3 className="text-sm font-semibold text-warning-foreground">Coverage Gaps</h3><ul className="mt-2 list-disc space-y-1 pl-4 text-xs leading-5 text-warning-foreground">{payload.coverage_gaps.map((gap)=><li key={gap}>{gap}</li>)}</ul></section>:null}</div>;
}

export function AnalysisCitationList({summary,onCitation}:{summary:SummaryRecord;onCitation:(page:number,chunkId?:string|null)=>void}){
  if(!summary.citations.length)return null;
  return <section className="rounded-xl border border-border p-3" data-testid="analysis-citations"><div className="flex items-center justify-between"><h3 className="text-sm font-semibold">Citations</h3><span className="text-xs text-muted-foreground">{summary.citations.length}</span></div><div className="mt-2 space-y-2">{summary.citations.map((citation)=><button key={citation.citation_id} onClick={()=>onCitation(citation.page_number??1,citation.chunk_id)} className="w-full rounded-lg bg-muted p-2 text-left text-xs hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"><span className="font-semibold text-primary">[{citation.citation_id}]</span><span className="ml-2 text-muted-foreground">{citation.page_number?`Page ${citation.page_number}`:'Page not provided'}{citation.section?` · ${citation.section}`:''}</span><p className="mt-1 line-clamp-3 leading-5 text-muted-foreground">{citation.excerpt||'Source excerpt unavailable.'}</p></button>)}</div></section>;
}

export function GenerateAnalysisDialog({open,type,length,busy,onClose,onGenerate}:{open:boolean;type:DocumentAnalysisType;length:DocumentAnalysisLength;busy:boolean;onClose:()=>void;onGenerate:(type:DocumentAnalysisType,length:DocumentAnalysisLength)=>void}){
  const[nextType,setNextType]=useState(type);const[nextLength,setNextLength]=useState(length);const closeRef=useRef<HTMLButtonElement>(null);
  useEffect(()=>{if(open){setNextType(type);setNextLength(length);setTimeout(()=>closeRef.current?.focus(),0)}},[open,type,length]);
  if(!open)return null;
  return <div className="fixed inset-0 z-[70] flex items-center justify-center bg-overlay p-4 backdrop-blur-[2px]" role="presentation" onMouseDown={(event)=>{if(event.target===event.currentTarget&&!busy)onClose()}}><div role="dialog" aria-modal="true" aria-labelledby="generate-analysis-title" className="w-full max-w-sm rounded-2xl border border-popover-border bg-popover p-5 text-popover-foreground shadow-2xl"><div className="flex items-start justify-between"><div><h2 id="generate-analysis-title" className="font-semibold text-heading-foreground">Generate document analysis</h2><p className="mt-1 text-xs leading-5 text-muted-foreground">Every length processes the complete current document version.</p></div><button ref={closeRef} onClick={onClose} disabled={busy} className="ce-icon-button" aria-label="Close analysis settings"><X size={16}/></button></div><label className="mt-4 block text-xs font-medium text-foreground">Type<select value={nextType} onChange={(event)=>setNextType(event.target.value as DocumentAnalysisType)} className="mt-1 h-10 w-full rounded-lg border border-border bg-secondary px-3 text-sm"><option value="overview">Overview</option><option value="detailed">Detailed</option><option value="key_points">Key points</option><option value="action_items">Action items</option></select></label><label className="mt-3 block text-xs font-medium text-foreground">Length<select value={nextLength} onChange={(event)=>setNextLength(event.target.value as DocumentAnalysisLength)} className="mt-1 h-10 w-full rounded-lg border border-border bg-secondary px-3 text-sm"><option value="brief">Brief</option><option value="standard">Standard</option><option value="detailed">Detailed</option></select></label><button onClick={()=>onGenerate(nextType,nextLength)} disabled={busy} className="ce-action ce-action-primary mt-5 h-10 w-full justify-center disabled:opacity-50">{busy?<LoaderCircle size={15} className="motion-safe:animate-spin"/>:<Sparkles size={15}/>}Generate</button></div></div>;
}

export default function DocumentAnalysisCard({document,onAsk,onCitation,onSuggestedQuestion}:{document:CorpusDocument;onAsk:(question?:string)=>Promise<void>;onCitation:(page:number,chunkId?:string|null)=>void;onSuggestedQuestion:(question:string)=>void}){
  const[type,setType]=useState<DocumentAnalysisType>('overview');const[length,setLength]=useState<DocumentAnalysisLength>('standard');const[dialog,setDialog]=useState(false);const[menu,setMenu]=useState(false);const queryClient=useQueryClient();const pollStartedAt=useRef(Date.now());
  const queryKey=['document-analysis',document.id,document.current_version_id??document.content_hash,type,length] as const;
  useEffect(()=>{pollStartedAt.current=Date.now();return()=>{void queryClient.cancelQueries({queryKey,exact:true})}},[document.id,document.current_version_id,document.content_hash,type,length,queryClient]);
  const analysis=useQuery({queryKey,queryFn:({signal})=>getDocumentAnalysis(document.id,type,length,signal),retry:false,placeholderData:(previous)=>previous,refetchIntervalInBackground:true,refetchInterval:(query)=>analysisPollInterval(pollStartedAt.current,typeof window!=='undefined'&&window.document.visibilityState==='hidden',query.state.data?.current?.status)});
  const generate=useMutation({mutationFn:(value:{type:DocumentAnalysisType;length:DocumentAnalysisLength;force:boolean})=>createDocumentAnalysis(document.id,{summary_type:value.type,length:value.length,force_regenerate:value.force}),onSuccess:(result,variables)=>{setType(variables.type);setLength(variables.length);setDialog(false);queryClient.setQueryData(['document-analysis',document.id,document.current_version_id??document.content_hash,variables.type,variables.length],{document_id:document.id,current_version_id:result.summary.document_version_id??'',summary_type:variables.type,length:variables.length,current:result.summary,previous:[]})}});
  const save=useMutation({mutationFn:(id:string)=>saveSummaryToSavedKnowledge(id)});
  const follow=useMutation({mutationFn:(id:string)=>askSummaryFollowUp(id,'original_versions'),onSuccess:(result)=>{
    window.location.assign(assistantConversationPath(result.chat_session_id));
  }});
  const current=analysis.data?.current??null;const previous=analysis.data?.previous?.[0]??null;const shown=current??previous;const active=current&&['queued','running'].includes(current.status);const failed=current?.status==='failed';const ready=shown&&['completed','stale'].includes(shown.status)&&shown.structured_payload;
  const doGenerate=(nextType:DocumentAnalysisType,nextLength:DocumentAnalysisLength,force=false)=>{if(generate.isPending||active)return;generate.mutate({type:nextType,length:nextLength,force})};
  if(analysis.isLoading)return <div className="rounded-xl border border-border p-4 text-sm text-muted-foreground">Loading document analysis…</div>;
  return <div className="space-y-3" data-testid="document-analysis-card">
    {!shown&&!analysis.isError?<section className="rounded-xl border border-dashed border-border bg-muted p-5 text-center"><FileSearch className="mx-auto text-muted-foreground" size={28}/><h2 className="mt-3 text-sm font-semibold text-foreground">Document analysis</h2><p className="mt-2 text-xs leading-5 text-muted-foreground">Generate a grounded summary, key findings, and citations for this document.</p><button onClick={()=>setDialog(true)} disabled={generate.isPending} className="ce-action ce-action-primary mt-4 h-10 px-4 disabled:opacity-50"><Sparkles size={15}/>Generate analysis</button><button onClick={()=>void onAsk()} className="ce-action mt-2 h-9 px-3 text-xs"><MessageSquareText size={14}/>Ask AI instead</button></section>:null}
    {analysis.isError?<section className="rounded-xl border border-destructive/30 bg-destructive/10 p-4 text-center"><AlertTriangle className="mx-auto text-destructive" size={24}/><h3 className="mt-2 text-sm font-semibold text-destructive">Analysis unavailable</h3><p className="mt-1 text-xs text-destructive">The document analysis endpoint could not be loaded.</p><button onClick={()=>void analysis.refetch()} className="ce-action mt-3 h-9 px-3"><RefreshCw size={14}/>Retry</button></section>:null}
    {active?<><AnalysisProgress progress={current?.progress}/><p className="px-1 text-[11px] text-muted-foreground">You can leave; analysis continues in background.</p></>:null}
    {failed?<section className="rounded-xl border border-destructive/30 bg-destructive/10 p-4"><h3 className="text-sm font-semibold text-destructive">Analysis failed</h3><p className="mt-1 text-xs text-destructive">{current?.error_message||'The local analysis could not be completed.'}</p>{current.retryable!==false?<button onClick={()=>doGenerate(type,length,true)} disabled={generate.isPending} className="ce-action mt-3 h-9 px-3"><RefreshCw size={14}/>Retry</button>:null}</section>:null}
    {ready&&shown?<><section className={cn('rounded-xl border p-3',shown.stale||shown.status==='stale'?'border-warning/30 bg-warning/10':'border-border bg-card')}><div className="flex items-start justify-between gap-2"><div><h2 className="text-sm font-semibold text-foreground">{shown.title}</h2><AnalysisVersionBadge summary={shown}/></div><div className="relative"><button onClick={()=>setMenu((value)=>!value)} className="ce-icon-button" aria-label="Analysis actions" aria-expanded={menu}><ChevronDown size={15}/></button>{menu?<div className="absolute right-0 top-10 z-10 w-44 rounded-lg border border-border bg-card p-1 text-xs shadow-lg"><button onClick={()=>{setMenu(false);doGenerate(type,length,true)}} className="w-full rounded-md px-3 py-2 text-left hover:bg-muted">Regenerate</button><button onClick={()=>{setMenu(false);setDialog(true)}} className="w-full rounded-md px-3 py-2 text-left hover:bg-muted">Change type or length</button></div>:null}</div></div>{shown.stale||shown.status==='stale'?<div className="mt-3 text-xs text-warning-foreground"><p>This analysis was generated for an earlier document version.</p><button onClick={()=>doGenerate(type,length,false)} className="ce-action mt-2 h-8 px-2">Generate updated analysis</button></div>:null}</section><AnalysisSections payload={shown.structured_payload!}/><AnalysisCitationList summary={shown} onCitation={onCitation}/>{shown.suggested_questions?.length?<section className="rounded-xl border border-border p-3"><h3 className="text-sm font-semibold">Suggested Follow-up Questions</h3><div className="mt-2 flex flex-wrap gap-2">{shown.suggested_questions.map((question)=><button key={question} onClick={()=>onSuggestedQuestion(question)} className="rounded-lg border border-border px-2 py-1.5 text-left text-xs hover:bg-muted">{question}</button>)}</div></section>:null}<div className="grid grid-cols-1 gap-2 sm:grid-cols-2"><button onClick={()=>follow.mutate(shown.id)} disabled={follow.isPending||shown.status==='stale'} className="ce-action ce-action-primary h-10 justify-center disabled:opacity-50"><MessageSquareText size={15}/>Ask about this summary</button><button onClick={()=>save.mutate(shown.id)} disabled={save.isPending} className="ce-action h-10 justify-center disabled:opacity-50"><BookmarkPlus size={15}/>{save.isSuccess?'Saved':'Save to Knowledge'}</button></div></>:null}
    {generate.isError?<p role="alert" className="rounded-lg bg-destructive/10 p-3 text-xs text-destructive">Analysis generation could not be queued. Try again.</p>:null}
    <GenerateAnalysisDialog open={dialog} type={type} length={length} busy={generate.isPending} onClose={()=>setDialog(false)} onGenerate={(nextType,nextLength)=>doGenerate(nextType,nextLength,false)}/>
  </div>;
}
