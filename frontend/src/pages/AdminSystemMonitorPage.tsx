import {
  Activity,
  Bot,
  Box,
  Cpu,
  Database,
  Gauge,
  HardDrive,
  RefreshCw,
  Server,
  ShieldCheck,
  Workflow,
  Zap,
} from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { useAuth } from '@/auth/AuthContext';
import AdminAccessDeniedPage from './AdminAccessDeniedPage';
import { useAdminSystemMonitor } from '@/hooks/useAdminSystemMonitor';
import type {
  AdminSystemMonitor,
  OperationsComponent,
  OperationsStatus,
} from '@/api/types';

const statusStyles: Record<OperationsStatus, string> = {
  green: 'border-emerald-200 bg-emerald-50 text-emerald-700',
  blue: 'border-blue-200 bg-blue-50 text-blue-700',
  yellow: 'border-amber-200 bg-amber-50 text-amber-700',
  red: 'border-red-200 bg-red-50 text-red-700',
};

const dotStyles: Record<OperationsStatus, string> = {
  green: 'bg-emerald-500',
  blue: 'bg-blue-500',
  yellow: 'bg-amber-500',
  red: 'bg-red-500',
};

function componentStatus(component: OperationsComponent | undefined): OperationsStatus {
  if (!component || component.available === false) return 'red';
  if (component.status === 'degraded' || component.available === null) return 'yellow';
  return 'green';
}

function formatNumber(value: number | null | undefined, suffix = '') {
  return value === null || value === undefined ? 'Unavailable' : `${value.toLocaleString()}${suffix}`;
}

function formatLatency(
  value: number | null | undefined,
  maximum?: number | null,
) {
  if (
    value === null
    || value === undefined
    || !Number.isFinite(value)
    || value < 0
    || (
      maximum !== null
      && maximum !== undefined
      && (!Number.isFinite(maximum) || value > maximum)
    )
  ) {
    return 'Unavailable';
  }
  return `${value.toLocaleString()} ms`;
}

function formatTime(value: string | null | undefined) {
  if (!value) return 'Not available';
  return new Intl.DateTimeFormat(undefined, {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
  }).format(new Date(value));
}

function Metric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-200 bg-slate-50/70 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold text-slate-950">{value}</div>
      {detail ? <div className="mt-1 truncate text-xs text-slate-500">{detail}</div> : null}
    </div>
  );
}

function OverviewCard({
  name,
  icon: Icon,
  status,
  detail,
  latency,
  updated,
}: {
  name: string;
  icon: LucideIcon;
  status: OperationsStatus;
  detail: string;
  latency?: number | null;
  updated?: string | null;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-[#eef6eb] p-2.5 text-[#2f6d25]">
            <Icon size={19} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-slate-950">{name}</h3>
            <p className="mt-0.5 text-xs text-slate-500">{detail}</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-bold uppercase ${statusStyles[status]}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${dotStyles[status]}`} />
          {status}
        </span>
      </div>
      <div className="mt-4 flex justify-between border-t border-slate-100 pt-3 text-xs text-slate-500">
        <span>{latency === undefined ? 'Live telemetry' : `${formatNumber(latency, ' ms')} latency`}</span>
        <span>{updated ? `Updated ${formatTime(updated)}` : 'Awaiting sample'}</span>
      </div>
    </article>
  );
}

const pipeline = [
  ['File Detection', 'pending'],
  ['Extraction', 'extracting'],
  ['Chunking', 'chunked'],
  ['Embedding', 'embedding'],
  ['Qdrant Writing', 'writing'],
  ['Generation Publishing', 'verifying'],
] as const;

function Pipeline({ data }: { data: AdminSystemMonitor }) {
  const activeStates = new Set(data.indexing.active_jobs.map((job) => String(job.status)));
  return (
    <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
      {pipeline.map(([label, state], index) => {
        const active = activeStates.has(state);
        return (
          <div key={state} className="relative">
            <div className={`h-full rounded-xl border p-3 transition ${active ? 'border-blue-300 bg-blue-50 shadow-sm' : 'border-slate-200 bg-slate-50'}`}>
              <div className="flex items-center justify-between">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${active ? 'bg-blue-600 text-white' : 'bg-white text-slate-500 ring-1 ring-slate-200'}`}>
                  {index + 1}
                </span>
                {active ? <Activity className="h-4 w-4 animate-pulse text-blue-600" /> : null}
              </div>
              <div className="mt-3 text-xs font-semibold text-slate-800">{label}</div>
              <div className="mt-1 text-[11px] text-slate-500">{active ? 'Active now' : 'Waiting'}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}

export default function AdminSystemMonitorPage() {
  const { user } = useAuth();
  const canAccess = Boolean(
    user?.permission_names.some((permission) =>
      ['monitor_system', 'manage_settings'].includes(permission),
    ),
  );
  if (!canAccess) return <AdminAccessDeniedPage />;
  return <AuthorizedMonitor />;
}

function AuthorizedMonitor() {
  const { data, connection, stale, error, reconnect } = useAdminSystemMonitor();
  if (!data) {
    return (
      <section className="flex min-h-[65vh] items-center justify-center">
        <div className="text-center">
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-[#2f6d25]" />
          <h1 className="mt-4 text-lg font-semibold text-slate-950">Connecting to operations telemetry</h1>
          <p className="mt-2 text-sm text-slate-500">{error ?? 'Authenticating the live monitor stream…'}</p>
        </div>
      </section>
    );
  }

  const telemetryStale = stale || data.stale;
  const q = data.query;
  const infrastructure = data.infrastructure;
  const updated = data.generated_at;
  return (
    <section className="mx-auto w-full max-w-[1600px] space-y-5 pb-10" data-testid="admin-system-monitor">
      <header className="rounded-2xl border border-[#dce7d8] bg-[linear-gradient(135deg,#173d1c_0%,#285f28_58%,#347538_100%)] p-5 text-white shadow-sm sm:p-6">
        <div className="flex flex-col justify-between gap-5 lg:flex-row lg:items-center">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-[0.16em] text-emerald-100">
              <ShieldCheck size={15} /> Administrator operations
            </div>
            <h1 className="mt-2 text-2xl font-semibold tracking-tight sm:text-3xl">AI Operations Console</h1>
            <p className="mt-2 max-w-2xl text-sm text-emerald-50/80">
              Live infrastructure, indexing, model, and query-pipeline telemetry.
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold ${telemetryStale ? 'border-amber-300/50 bg-amber-300/15 text-amber-50' : 'border-white/20 bg-white/10 text-white'}`}>
              <span className={`h-2 w-2 rounded-full ${connection === 'live' && !telemetryStale ? 'bg-emerald-300 animate-pulse' : 'bg-amber-300'}`} />
              {telemetryStale ? 'Stale telemetry' : connection === 'live' ? 'Live stream connected' : connection}
            </span>
            <button type="button" onClick={reconnect} className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-white/10 px-3 py-2 text-xs font-semibold text-white hover:bg-white/15">
              <RefreshCw size={14} /> Reconnect
            </button>
          </div>
        </div>
      </header>

      {error || telemetryStale ? (
        <div role="status" className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-800">
          {error || 'One or more telemetry sources are stale. Last known values remain visible.'}
        </div>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <OverviewCard name="Backend" icon={Server} status={componentStatus(infrastructure.backend)} detail="API runtime" latency={infrastructure.backend.latency_ms} updated={updated} />
        <OverviewCard name="Database" icon={Database} status={componentStatus(infrastructure.postgresql)} detail="PostgreSQL metadata" latency={infrastructure.postgresql.latency_ms} updated={updated} />
        <OverviewCard name="Qdrant" icon={HardDrive} status={componentStatus(infrastructure.qdrant)} detail="Vector collection" latency={infrastructure.qdrant.latency_ms} updated={updated} />
        <OverviewCard name="Indexer" icon={Workflow} status={data.indexing.worker_stale ? 'yellow' : data.indexing.state === 'updating' ? 'blue' : 'green'} detail={data.indexing.worker_status} updated={updated} />
        <OverviewCard name="GPU" icon={Zap} status={data.gpu.cuda_available ? 'green' : 'yellow'} detail={data.gpu.device} updated={updated} />
        <OverviewCard name="Models" icon={Bot} status={data.models.ollama_available && data.models.embedding_model_ready ? 'green' : 'red'} detail={`${data.models.loaded_models.length} loaded`} updated={updated} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.7fr_1fr]">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div><h2 className="font-semibold text-slate-950">Live indexing pipeline</h2><p className="mt-1 text-xs text-slate-500">Durable job state and publication flow</p></div>
            <span className="text-xs font-medium text-slate-500">Generation {data.indexing.active_published_generation}</span>
          </div>
          <div className="mt-5"><Pipeline data={data} /></div>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="Queue depth" value={data.indexing.queue_depth} />
            <Metric label="Completed" value={data.indexing.completed_jobs} />
            <Metric label="Throughput" value={formatNumber(data.indexing.throughput.documents_per_hour, '/hr')} />
            <Metric label="Failures" value={data.indexing.failed_jobs} />
          </div>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2"><Gauge size={18} className="text-[#2f6d25]" /><h2 className="font-semibold text-slate-950">GPU monitoring</h2></div>
          <div className="mt-5 space-y-4">
            <div>
              <div className="flex justify-between text-xs"><span className="text-slate-500">Utilisation</span><span className="font-semibold">{formatNumber(data.gpu.utilization_percent, '%')}</span></div>
              <div className="mt-2 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-[#4a8a3d] transition-all" style={{ width: `${Math.min(data.gpu.utilization_percent ?? 0, 100)}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs"><span className="text-slate-500">VRAM</span><span className="font-semibold">{data.gpu.memory_used_mb === null ? 'Unavailable' : `${data.gpu.memory_used_mb} / ${data.gpu.memory_total_mb} MB`}</span></div>
              <div className="mt-2 h-2 rounded-full bg-slate-100"><div className="h-2 rounded-full bg-blue-500 transition-all" style={{ width: `${data.gpu.memory_total_mb ? Math.min((data.gpu.memory_used_mb ?? 0) / data.gpu.memory_total_mb * 100, 100) : 0}%` }} /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Metric label="Precision" value={data.gpu.precision} />
              <Metric label="Batch size" value={data.gpu.batch_size} />
              <Metric label="Device" value={data.gpu.embedding_device} />
              <Metric label="Configured device" value={data.gpu.embedding_device_configured ?? 'unknown'} />
              <Metric label="Actual model device" value={data.gpu.embedding_device_actual ?? 'unknown'} />
              <Metric label="Embedding model" value={data.gpu.embedding_model_status ?? 'unknown'} />
              <Metric label="Batch latency" value={formatNumber(data.gpu.embedding_batch?.duration_ms, ' ms')} />
            <Metric label="Query embedding" value={data.models.query_embedding_device ?? 'unknown'} detail={[data.models.query_embedding_dtype, data.models.query_embedding_model_state].filter(Boolean).join(' · ') || undefined} />
            <Metric label="Dense model" value={data.models.dense_model_status ?? 'unavailable'} />
            <Metric label="Reranker status" value={data.models.reranker_status ?? 'unavailable'} />
            <Metric label="Reranker device" value={data.models.reranker_device ?? 'Unavailable'} detail={data.models.reranker_dtype ?? undefined} />
            <Metric label="BM25 runtime" value={data.models.bm25_status ?? 'unavailable'} />
              <Metric label="GPU state" value={data.gpu.state ?? 'unknown'} />
              <Metric label="Embedding jobs" value={data.gpu.active_embedding_jobs ?? 0} />
              <Metric label="Chat priority" value={data.gpu.chat_priority_active ? 'active' : 'idle'} />
              <Metric label="Chunks / min" value={formatNumber(data.gpu.embedding_throughput_chunks_per_minute)} />
            </div>
          </div>
        </article>
      </div>

      <div className="grid gap-5 lg:grid-cols-3">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2"><Cpu size={18} className="text-[#2f6d25]" /><h2 className="font-semibold">Worker monitoring</h2></div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Metric label="CPU workers" value={data.cpu.extraction_workers} />
            <Metric label="GPU workers" value={data.indexing.active_workers} />
            <Metric label="OCR workers" value={data.cpu.ocr_workers} />
            <Metric label="Active tasks" value={data.cpu.current_tasks} />
          </div>
          <p className="mt-4 text-xs text-slate-500">Heartbeat {formatTime(data.indexing.worker_heartbeat_at)} · CPU {formatNumber(data.cpu.utilization_percent, '%')}</p>
        </article>

        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center gap-2"><Activity size={18} className="text-[#2f6d25]" /><h2 className="font-semibold">Query pipeline</h2></div>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <Metric label="Active" value={q.active_chat_requests} />
            <Metric label="Current stage" value={q.current_stage ?? 'Idle'} detail={q.current_stage_duration_ms === null ? undefined : `${q.current_stage_duration_ms} ms active`} />
            <Metric label="Validation" value={formatNumber(q.validation_latency_ms, ' ms')} />
            <Metric label="Retrieval" value={formatNumber(q.retrieval_latency_ms, ' ms')} />
            <Metric label="Parallel retrieval" value={formatNumber(q.parallel_retrieval_duration_ms, ' ms')} detail={q.dense_completed && q.bm25_completed ? 'Dense + BM25 completed' : undefined} />
            <Metric label="Query embedding latency" value={formatNumber(q.query_embedding_metrics?.query_embedding_duration_ms, ' ms')} detail={q.query_embedding_metrics?.query_embedding_cache_status} />
            <Metric label="Qdrant search" value={formatNumber(q.qdrant_metrics?.qdrant_search_latency_ms, ' ms')} detail={q.qdrant_index_status ?? undefined} />
            <Metric label="Retrieval cache" value={q.retrieval_cache_metrics?.retrieval_cache_hit ? 'hit' : q.retrieval_cache_metrics?.retrieval_cache_miss ? 'miss' : 'Unavailable'} detail={`${q.retrieval_cache_size ?? 0} entries · ${formatNumber(q.retrieval_cache_metrics?.retrieval_cache_latency_ms, ' ms')}`} />
            <Metric label="BM25 search" value={formatNumber(q.bm25_search_duration_ms, ' ms')} />
            <Metric label="BM25 candidates" value={q.bm25_candidate_count ?? 'Unavailable'} />
            <Metric label="BM25 chunks" value={q.bm25_chunk_count} detail={`${q.bm25_document_count} documents`} />
            <Metric label="BM25 snapshot" value={q.bm25_snapshot_size === null ? 'Unavailable' : `${(q.bm25_snapshot_size / 1_048_576).toFixed(1)} MB`} detail={q.bm25_snapshot_loaded_at ? `Loaded ${formatTime(q.bm25_snapshot_loaded_at)}` : undefined} />
            <Metric label="BM25 load" value={formatNumber(q.bm25_snapshot_load_duration_ms, ' ms')} />
            <Metric label="BM25 activation" value={formatNumber(q.bm25_index_activation_duration_ms, ' ms')} />
            <Metric label="Reranking" value={formatNumber(q.reranker_latency_ms, ' ms')} />
            <Metric label="Reranker batch" value={q.reranker_metrics?.reranker_batch_size ?? 'Unavailable'} detail={q.reranker_metrics?.reranker_candidate_count === undefined ? undefined : `${q.reranker_metrics.reranker_candidate_count} candidates`} />
            <Metric label="Generation" value={formatLatency(q.generation_latency_ms, q.total_latency_ms)} />
            <Metric label="First token" value={formatLatency(q.generation_metrics?.first_token_ms, q.generation_latency_ms)} />
            <Metric label="Tokens / sec" value={formatNumber(q.generation_metrics?.tokens_per_second)} />
            <Metric label="Model load" value={formatLatency(q.generation_metrics?.model_load_ms, q.generation_latency_ms)} />
            <Metric label="Ollama processor" value={q.generation_metrics?.ollama_processor_type ?? 'Unavailable'} />
            <Metric label="GPU layers" value={q.generation_metrics?.gpu_layers_used ?? 'Unavailable'} detail={q.generation_metrics?.gpu_layers_requested === -1 ? 'all requested' : undefined} />
            <Metric label="Generation GPU" value={formatNumber(q.generation_metrics?.generation_gpu_utilization, '%')} detail={q.generation_metrics?.generation_gpu_utilization_peak === undefined ? undefined : `${q.generation_metrics.generation_gpu_utilization_peak}% peak`} />
            <Metric label="Ollama VRAM" value={q.generation_metrics?.gpu_memory_used === undefined ? 'Unavailable' : `${q.generation_metrics.gpu_memory_used} / ${q.generation_metrics.gpu_memory_total ?? '?'} MB`} />
            <Metric label="CPU offload" value={q.generation_metrics?.cpu_offload_detected === null || q.generation_metrics?.cpu_offload_detected === undefined ? 'Unavailable' : q.generation_metrics.cpu_offload_detected ? 'detected' : 'none'} />
          </div>
          {q.failed_stage ? (
            <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900">
              Failed stage: <strong>{q.failed_stage}</strong>
              {q.timeout_reason ? ` · Timeout: ${q.timeout_reason}` : ''}
            </div>
          ) : null}
        </article>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1.35fr]">
        <article className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <div className="flex items-center gap-2"><Box size={18} className="text-[#2f6d25]" /><h2 className="font-semibold">Queue management</h2></div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="Pending" value={data.indexing.pending_jobs} />
            <Metric label="Processing" value={data.indexing.active_jobs_count} />
            <Metric label="Failed" value={data.indexing.failed_jobs} />
          </div>
          <div className="mt-4 space-y-2">
            {Object.entries(data.indexing.priority_queues).map(([name, count]) => (
              <div key={name} className="flex items-center justify-between rounded-lg border border-slate-100 px-3 py-2 text-xs"><span className="font-medium text-slate-700">{name.replaceAll('_', ' ')}</span><span className="font-bold text-slate-950">{count}</span></div>
            ))}
            {!Object.keys(data.indexing.priority_queues).length ? <p className="py-3 text-center text-xs text-slate-500">No queued operations.</p> : null}
          </div>
        </article>

        <article className="overflow-hidden rounded-2xl border border-slate-200 bg-[#101814] text-slate-100 shadow-sm">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-4"><div className="flex items-center gap-2"><Activity size={17} className="text-emerald-400" /><h2 className="font-semibold">Live event stream</h2></div><span className="text-[11px] uppercase tracking-wider text-slate-400">{data.events.length} retained</span></div>
          <div className="max-h-[390px] overflow-y-auto">
            {data.events.map((event) => (
              <div key={event.id} className="grid grid-cols-[78px_10px_1fr] gap-3 border-b border-white/5 px-5 py-3 text-xs">
                <time className="font-mono text-slate-500">{formatTime(event.timestamp)}</time>
                <span className={`mt-1 h-2 w-2 rounded-full ${event.severity === 'error' ? 'bg-red-400' : event.severity === 'warning' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                <div><div className="font-mono text-emerald-300">{event.type}</div><div className="mt-1 text-slate-300">{event.message}</div></div>
              </div>
            ))}
            {!data.events.length ? <div className="px-5 py-10 text-center text-sm text-slate-400">Waiting for runtime state transitions…</div> : null}
          </div>
        </article>
      </div>
    </section>
  );
}
