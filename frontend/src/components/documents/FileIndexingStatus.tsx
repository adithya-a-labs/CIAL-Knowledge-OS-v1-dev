import { useEffect, useRef, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { Ban, CheckCircle2, CircleAlert, Clock3, LoaderCircle } from 'lucide-react';
import { retryDocumentIndexing } from '@/api/client';
import { useToast } from '@/hooks/use-toast';
import { cn } from '@/lib/utils';

export type FileIndexingState = 'pending' | 'indexing' | 'indexed' | 'failed' | 'deleted' | string;

export function indexingStatusPresentation(status: FileIndexingState) {
  if (status === 'indexed') return { label: 'Ready', Icon: CheckCircle2, tone: 'text-emerald-700 bg-emerald-50' };
  if (status === 'failed') return { label: 'Failed', Icon: CircleAlert, tone: 'text-rose-700 bg-rose-50' };
  if (status === 'deleted' || status === 'superseded') return { label: 'Unavailable', Icon: Ban, tone: 'text-slate-500 bg-slate-100' };
  if (status === 'indexing') return { label: 'Preparing', Icon: LoaderCircle, tone: 'text-amber-700 bg-amber-50', spinning: true };
  return { label: 'Queued', Icon: Clock3, tone: 'text-slate-600 bg-slate-100' };
}

interface FileIndexingStatusProps {
  status: FileIndexingState;
  stage?: string | null;
  safeMessage?: string | null;
  retryAllowed?: boolean;
  documentId?: string;
  fileName?: string;
  compact?: boolean;
  className?: string;
  onRetryAccepted?: () => void;
}

export default function FileIndexingStatus({ status, stage, safeMessage, retryAllowed = false, documentId, fileName, compact = false, className, onRetryAccepted }: FileIndexingStatusProps) {
  const queryClient = useQueryClient();
  const { toast } = useToast();
  const requestLock = useRef(false);
  const [isRetrying, setIsRetrying] = useState(false);
  const [accepted, setAccepted] = useState(false);
  useEffect(() => { if (status !== 'failed') setAccepted(false); }, [status]);
  const effectiveStatus = isRetrying || accepted ? 'pending' : status;
  const value = indexingStatusPresentation(effectiveStatus);
  const terminal = ['indexed', 'failed', 'deleted', 'superseded'].includes(effectiveStatus);
  const canRetry = status === 'failed' && retryAllowed && Boolean(documentId) && !accepted;
  const label = fileName ? `Retry indexing ${fileName}` : 'Retry indexing';

  const retry = async () => {
    if (!canRetry || requestLock.current || !documentId) return;
    requestLock.current = true; setIsRetrying(true);
    try {
      const result = await retryDocumentIndexing(documentId);
      setAccepted(true);
      queryClient.setQueryData(['document-indexing-statuses', [documentId]], { [documentId]: result });
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['document-indexing-statuses'] }),
        queryClient.invalidateQueries({ queryKey: ['my-workspace-folder'] }),
        queryClient.invalidateQueries({ queryKey: ['my-workspace-summary'] }),
        queryClient.invalidateQueries({ queryKey: ['corpus-folder'] }),
        queryClient.invalidateQueries({ queryKey: ['corpus-tree'] }),
        queryClient.invalidateQueries({ queryKey: ['corpus-document', documentId] }),
      ]);
      onRetryAccepted?.();
      toast({ title: 'Indexing restarted' });
    } catch (error) {
      setAccepted(false);
      toast({ title: 'Indexing retry failed', description: error instanceof Error ? error.message : safeMessage || 'Indexing could not be restarted.', variant: 'destructive' });
    } finally {
      requestLock.current = false; setIsRetrying(false);
    }
  };

  const content = <>
    <span className="inline-flex h-3.5 w-3.5 items-center justify-center"><value.Icon size={12} className={value.spinning || isRetrying ? 'animate-spin motion-reduce:animate-none' : undefined}/></span>
    {!compact ? <span>{value.label}</span> : null}
  </>;
  const classes = cn('inline-flex h-6 min-w-[3.75rem] shrink-0 items-center justify-center gap-1 rounded-full px-1.5 text-[10px] font-semibold', value.tone, className);
  if (canRetry) return <button type="button" className={cn(classes, 'cursor-pointer transition hover:ring-2 hover:ring-rose-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rose-400')}
    onClick={() => void retry()} disabled={isRetrying} title={safeMessage || 'Retry indexing'} aria-label={label} aria-live="polite">
    {content}
  </button>;
  return <span className={classes} title={safeMessage || stage || value.label} aria-label={`File status: ${value.label}`} aria-live={terminal ? 'polite' : 'off'}>{content}</span>;
}
