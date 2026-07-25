import { useState } from 'react';
import { Activity, ChevronDown } from 'lucide-react';
import { useSystemStatus } from '@/hooks/useSystemStatus';
import { cn } from '@/lib/utils';

const colors = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-800',
  blue: 'border-blue-200 bg-blue-50 text-blue-800',
  yellow: 'border-amber-200 bg-amber-50 text-amber-900',
  red: 'border-red-200 bg-red-50 text-red-800',
} as const;

const dots = {
  green: 'bg-emerald-500',
  blue: 'bg-blue-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500',
} as const;

export default function AssistantSystemHealth() {
  const [expanded, setExpanded] = useState(false);
  const query = useSystemStatus();
  const status = query.data;
  const color = query.isError ? 'red' : status?.status ?? 'yellow';
  const label = query.isError ? 'Unavailable' : status?.label ?? 'Degraded';

  return (
    <div className="relative" data-testid="assistant-system-health">
      <button
        type="button"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
        aria-controls="assistant-system-health-details"
        className={cn(
          'inline-flex min-h-8 items-center gap-2 rounded-full border px-3 text-xs font-semibold transition focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ring',
          colors[color],
        )}
      >
        <span className={cn('h-2 w-2 rounded-full', dots[color], color === 'blue' && 'motion-safe:animate-pulse')} />
        {label}
        <ChevronDown size={13} className={cn('transition-transform', expanded && 'rotate-180')} />
      </button>

      {expanded ? (
        <div
          id="assistant-system-health-details"
          className="absolute right-0 top-10 z-40 w-[min(22rem,calc(100vw-1.5rem))] rounded-xl border border-slate-200 bg-white p-4 text-xs text-slate-700 shadow-xl"
        >
          <div className="mb-3 flex items-center gap-2 font-semibold text-slate-950">
            <Activity size={15} />
            AI Assistant runtime
          </div>
          {status ? (
            <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-2">
              <dt className="text-slate-500">Generation</dt>
              <dd className="truncate text-right font-medium">{status.index.generation || 'None published'}</dd>
              <dt className="text-slate-500">Queue</dt>
              <dd className="text-right font-medium">{status.indexing.queue_depth} active</dd>
              <dt className="text-slate-500">Worker</dt>
              <dd className="truncate text-right font-medium">{status.indexing.worker_state}</dd>
              <dt className="text-slate-500">GPU</dt>
              <dd className="truncate text-right font-medium">
                {status.gpu.available ? `${status.gpu.utilization_percent ?? 0}% · ${status.gpu.device}` : 'Not available'}
              </dd>
              <dt className="text-slate-500">Model</dt>
              <dd className="truncate text-right font-medium" title={status.models.ollama}>{status.models.ollama}</dd>
              <dt className="text-slate-500">Checked</dt>
              <dd className="text-right font-medium">{new Date(status.timestamps.generated_at).toLocaleTimeString()}</dd>
            </dl>
          ) : (
            <p>{query.isError ? 'The live status endpoint could not be reached.' : 'Checking live component status…'}</p>
          )}
        </div>
      ) : null}
    </div>
  );
}
