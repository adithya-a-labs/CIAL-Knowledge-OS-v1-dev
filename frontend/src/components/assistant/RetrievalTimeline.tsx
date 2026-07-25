import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import type { GenerationEvent } from '@/api/types';

const labels: Record<string, string> = {
  'request.validating': 'Searching knowledge', 'context.building': 'Searching knowledge',
  'index_generation.loaded': 'Searching knowledge', dense_retrieval: 'Retrieving sources',
  bm25: 'Retrieving sources', hybrid_fusion: 'Retrieving sources',
  'retrieval.searching': 'Retrieving sources', reranking: 'Retrieving sources',
  'evidence.selecting': 'Retrieving sources', generation: 'Generating answer',
  'citations.linking': 'Completing answer', 'persistence.saving': 'Completing answer',
  chat: 'Completed',
};

export default function RetrievalTimeline({ events, elapsedSeconds, onStop }: { events: GenerationEvent[]; elapsedSeconds: number; onStop: () => void }) {
  const [expanded, setExpanded] = useState(false);
  const latest = events.at(-1); const current = latest ? labels[latest.stage_id] ?? latest.stage_id : 'Starting request';
  const completed = events.filter((event, index) => event.status === 'completed' && events.findIndex((item) => item.stage_id === event.stage_id && item.status === 'completed') === index);
  return (
    <div className="max-w-[46rem] py-1 text-sm text-slate-600" data-testid="inline-generation-status" role="status" aria-live="polite">
      <div className="flex min-w-0 items-center gap-2">
        <span className="h-4 w-4 shrink-0 rounded-full border-2 border-[#c8d8c3] border-t-primary motion-safe:animate-spin" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate font-medium text-slate-800">{current}<span className="motion-safe:animate-pulse">…</span></span>
        <time className="shrink-0 tabular-nums text-xs text-slate-500">{Math.floor(elapsedSeconds / 60)}:{String(elapsedSeconds % 60).padStart(2, '0')}</time>
        <button type="button" onClick={onStop} className="shrink-0 rounded px-1.5 py-1 text-xs font-semibold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary hover:text-red-700" aria-label="Stop generation">Stop</button>
      </div>
      <button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} aria-controls="generation-details" className="mt-1 inline-flex items-center gap-1 rounded px-6 py-1 text-xs hover:text-slate-900 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{expanded ? 'Show less' : 'Show details'}{expanded ? <ChevronUp size={13}/> : <ChevronDown size={13}/>}</button>
      {expanded ? <ol id="generation-details" className="ml-7 mt-1 space-y-1 border-l border-slate-200 pl-3 text-xs">
        {completed.map((event) => <li key={`${event.stage_id}-${event.elapsed_ms}`} className="flex items-start gap-2"><Check size={13} className="mt-0.5 shrink-0 text-primary"/><span>{labels[event.stage_id] ?? event.stage_id}{Object.keys(event.metrics ?? {}).length ? ` · ${Object.entries(event.metrics ?? {}).map(([key,value]) => `${String(value)} ${key.replaceAll('_',' ')}`).join(' · ')}` : ''}</span></li>)}
        {latest?.status === 'started' ? <li className="flex items-center gap-2 font-medium text-slate-800"><span className="h-1.5 w-1.5 rounded-full bg-primary motion-safe:animate-pulse" />{current}</li> : null}
      </ol> : null}
    </div>
  );
}
