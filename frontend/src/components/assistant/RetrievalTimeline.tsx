import { Check, ChevronDown, ChevronUp } from 'lucide-react';
import { useState } from 'react';
import type { GenerationEvent } from '@/api/types';

const labels: Record<string, string> = {
  connection: 'Connected',
  queued: 'Queued',
  waiting_for_query_embedding: 'Waiting to search',
  searching: 'Searching knowledge',
  waiting_for_reranker: 'Waiting to rerank',
  waiting_for_generation: 'Waiting to generate',
  generating: 'Generating answer',
  persisting: 'Saving conversation',
  'request.validating': 'Validating request',
  'context.building': 'Validating request',
  'index_generation.loaded': 'Loading published generation',
  dense_retrieval: 'Searching knowledge',
  bm25: 'Searching knowledge',
  bm25_retrieval: 'Searching knowledge',
  hybrid_fusion: 'Searching knowledge',
  'retrieval.searching': 'Searching knowledge',
  reranking: 'Reranking sources',
  'evidence.selecting': 'Reranking sources',
  evidence_selection: 'Reranking sources',
  generation: 'Generating answer',
  'citations.linking': 'Generating answer',
  'persistence.saving': 'Generating answer',
  chat: 'Completed',
  complete: 'Completed',
  error: 'Failed',
};

function metricSummary(event: GenerationEvent) {
  const metrics = event.metrics ?? {};
  const values = [
    typeof metrics.duration_ms === 'number' ? `${metrics.duration_ms} ms` : null,
    typeof metrics.candidate_count === 'number'
      ? `${metrics.candidate_count} candidates`
      : null,
    metrics.error_state ? `failed: ${String(metrics.error_state)}` : null,
  ].filter(Boolean);
  return values.length ? ` · ${values.join(' · ')}` : '';
}

export default function RetrievalTimeline({
  events,
  elapsedSeconds,
  onStop,
  requestId,
}: {
  events: GenerationEvent[];
  elapsedSeconds: number;
  onStop: () => void;
  requestId: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const latest = events.at(-1);
  const current = latest
    ? labels[latest.stage_id] ?? latest.stage_id
    : 'Connecting';
  const completed = events.filter(
    (event, index) =>
      event.status === 'completed'
      && events.findIndex(
        (item) =>
          item.stage_id === event.stage_id && item.status === 'completed',
      ) === index,
  );
  return (
    <div className="max-w-[46rem] py-1 text-sm text-muted-foreground" data-testid="inline-generation-status" role="status" aria-live="polite">
      <div className="flex min-w-0 items-center gap-2">
        <span className="h-4 w-4 shrink-0 rounded-full border-2 border-[#c8d8c3] border-t-primary motion-safe:animate-spin" aria-hidden="true" />
        <span className="min-w-0 flex-1 truncate font-medium text-foreground">{current}<span className="motion-safe:animate-pulse">…</span></span>
        <time className="shrink-0 tabular-nums text-xs text-muted-foreground">{Math.floor(elapsedSeconds / 60)}:{String(elapsedSeconds % 60).padStart(2, '0')}</time>
        <button type="button" onClick={onStop} className="shrink-0 rounded px-1.5 py-1 text-xs font-semibold text-primary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary hover:text-destructive" aria-label={`Stop request ${requestId}`}>Stop</button>
      </div>
      <button type="button" onClick={() => setExpanded((value) => !value)} aria-expanded={expanded} aria-controls={`generation-details-${requestId}`} className="mt-1 inline-flex items-center gap-1 rounded px-6 py-1 text-xs hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary">{expanded ? 'Show less' : 'Show details'}{expanded ? <ChevronUp size={13}/> : <ChevronDown size={13}/>}</button>
      {expanded ? <ol id={`generation-details-${requestId}`} className="ml-7 mt-1 space-y-1 border-l border-border pl-3 text-xs">
        {completed.map((event) => <li key={`${event.stage_id}-${event.elapsed_ms}`} className="flex items-start gap-2"><Check size={13} className="mt-0.5 shrink-0 text-primary"/><span>{labels[event.stage_id] ?? event.stage_id}{metricSummary(event)}</span></li>)}
        {latest?.status === 'started' ? <li className="flex items-center gap-2 font-medium text-foreground"><span className="h-1.5 w-1.5 rounded-full bg-primary motion-safe:animate-pulse" />{current}</li> : null}
      </ol> : null}
    </div>
  );
}
