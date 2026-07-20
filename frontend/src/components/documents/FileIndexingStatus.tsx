import { Ban, CheckCircle2, CircleAlert, Clock3, LoaderCircle } from 'lucide-react';
import { cn } from '@/lib/utils';

export type FileIndexingState = 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted' | string;

export function indexingStatusPresentation(status: FileIndexingState) {
  if (status === 'indexed') return { label: 'Ready', Icon: CheckCircle2, tone: 'text-emerald-700 bg-emerald-50' };
  if (status === 'failed') return { label: 'Failed', Icon: CircleAlert, tone: 'text-rose-700 bg-rose-50' };
  if (status === 'deleted' || status === 'superseded') return { label: 'Unavailable', Icon: Ban, tone: 'text-slate-500 bg-slate-100' };
  if (status === 'indexing') return { label: 'Preparing', Icon: LoaderCircle, tone: 'text-amber-700 bg-amber-50', spinning: true };
  return { label: 'Queued', Icon: Clock3, tone: 'text-slate-600 bg-slate-100' };
}

export default function FileIndexingStatus({ status, safeMessage, compact = false, className }: { status: FileIndexingState; safeMessage?: string | null; compact?: boolean; className?: string }) {
  const value = indexingStatusPresentation(status); const terminal = ['indexed', 'failed', 'deleted', 'superseded'].includes(status);
  return <span className={cn('inline-flex h-6 shrink-0 items-center gap-1 rounded-full px-1.5 text-[10px] font-semibold', value.tone, className)}
    title={safeMessage || value.label} aria-label={`File status: ${value.label}`} aria-live={terminal ? 'polite' : 'off'}>
    <span className="inline-flex h-3.5 w-3.5 items-center justify-center"><value.Icon size={12} className={value.spinning ? 'animate-spin motion-reduce:animate-none' : undefined}/></span>
    {!compact ? <span>{value.label}</span> : null}
  </span>;
}
