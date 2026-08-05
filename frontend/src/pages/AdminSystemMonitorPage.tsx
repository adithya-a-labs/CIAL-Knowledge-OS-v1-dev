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
  Wifi,
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
  blue: 'border-info/30 bg-info/10 text-info-foreground',
  yellow: 'border-warning/30 bg-warning/10 text-warning-foreground',
  red: 'border-destructive/30 bg-destructive/10 text-destructive',
};

const dotStyles: Record<OperationsStatus, string> = {
  green: 'bg-emerald-500',
  blue: 'bg-info/100',
  yellow: 'bg-warning/100',
  red: 'bg-destructive/100',
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
    <div className="rounded-xl border border-border bg-muted/70 p-3">
      <div className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
        {label}
      </div>
      <div className="mt-1 text-lg font-semibold text-foreground">{value}</div>
      {detail ? <div className="mt-1 truncate text-xs text-muted-foreground">{detail}</div> : null}
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
    <article className="rounded-2xl border border-border bg-card p-4 shadow-sm transition-colors">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <div className="rounded-xl bg-accent p-2.5 text-primary">
            <Icon size={19} />
          </div>
          <div>
            <h3 className="text-sm font-semibold text-foreground">{name}</h3>
            <p className="mt-0.5 text-xs text-muted-foreground">{detail}</p>
          </div>
        </div>
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-1 text-[11px] font-bold uppercase ${statusStyles[status]}`}>
          <span className={`h-1.5 w-1.5 rounded-full ${dotStyles[status]}`} />
          {status}
        </span>
      </div>
      <div className="mt-4 flex justify-between border-t border-border pt-3 text-xs text-muted-foreground">
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
            <div className={`h-full rounded-xl border p-3 transition ${active ? 'border-info/40 bg-info/10 shadow-sm' : 'border-border bg-muted'}`}>
              <div className="flex items-center justify-between">
                <span className={`flex h-7 w-7 items-center justify-center rounded-full text-xs font-bold ${active ? 'bg-blue-600 text-white' : 'bg-card text-muted-foreground ring-1 ring-border'}`}>
                  {index + 1}
                </span>
                {active ? <Activity className="h-4 w-4 animate-pulse text-info" /> : null}
              </div>
              <div className="mt-3 text-xs font-semibold text-foreground">{label}</div>
              <div className="mt-1 text-[11px] text-muted-foreground">{active ? 'Active now' : 'Waiting'}</div>
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
          <RefreshCw className="mx-auto h-8 w-8 animate-spin text-primary" />
          <h1 className="mt-4 text-lg font-semibold text-foreground">Connecting to operations telemetry</h1>
          <p className="mt-2 text-sm text-muted-foreground">{error ?? 'Authenticating the live monitor stream…'}</p>
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
            <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-2 text-xs font-semibold ${telemetryStale ? 'border-warning/40/50 bg-amber-300/15 text-amber-50' : 'border-white/20 bg-card/10 text-white'}`}>
              <span className={`h-2 w-2 rounded-full ${connection === 'live' && !telemetryStale ? 'bg-emerald-300 animate-pulse' : 'bg-amber-300'}`} />
              {telemetryStale ? 'Stale telemetry' : connection === 'live' ? 'Live stream connected' : connection}
            </span>
            <button type="button" onClick={reconnect} className="inline-flex items-center gap-2 rounded-full border border-white/20 bg-card/10 px-3 py-2 text-xs font-semibold text-white hover:bg-card/15">
              <RefreshCw size={14} /> Reconnect
            </button>
          </div>
        </div>
      </header>

      {error || telemetryStale ? (
        <div role="status" className="rounded-xl border border-warning/30 bg-warning/10 px-4 py-3 text-sm text-warning-foreground">
          {error || 'One or more telemetry sources are stale. Last known values remain visible.'}
        </div>
      ) : null}

      <article className="rounded-2xl border border-border bg-card p-5 shadow-sm" data-testid="lan-server-status">
        <div className="flex flex-col gap-5 md:flex-row md:items-start md:justify-between">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <Wifi size={18} className="text-primary" />
              <h2 className="font-semibold text-foreground">LAN Server</h2>
              <span className={`rounded-full border px-2 py-0.5 text-[11px] font-bold uppercase ${data.lan_access.gateway_ready ? statusStyles.green : data.lan_access.enabled ? statusStyles.yellow : statusStyles.red}`}>
                {data.lan_access.gateway_ready ? 'LAN ready' : data.lan_access.enabled ? 'Waiting' : 'Local only'}
              </span>
            </div>
            <p className="mt-2 text-sm text-muted-foreground">{data.lan_access.safe_detail}</p>
            <div className="mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <Metric label="Gateway" value={data.lan_access.gateway_ready ? 'ready' : 'unavailable'} />
              <Metric label="mDNS" value={data.lan_access.discovery_ready ? 'registered' : 'unavailable'} />
              <Metric label="Firewall" value={data.lan_access.firewall_state} />
              <Metric label="Transport" value={data.lan_access.scheme.toUpperCase()} detail={data.lan_access.scheme === 'http' ? 'Unencrypted controlled-hotspot mode' : `TLS ${data.lan_access.tls_state}`} />
            </div>
            <div className="mt-4 space-y-1 text-sm">
              {data.lan_access.domain_url ? <div><span className="text-muted-foreground">Domain:</span> <a className="font-medium text-primary underline-offset-4 hover:underline" href={data.lan_access.domain_url}>{data.lan_access.domain_url}</a></div> : null}
              {data.lan_access.ip_fallback_url ? <div><span className="text-muted-foreground">IP fallback:</span> <a className="font-medium text-primary underline-offset-4 hover:underline" href={data.lan_access.ip_fallback_url}>{data.lan_access.ip_fallback_url}</a></div> : null}
              <div className="text-xs text-muted-foreground">Hotspot {data.lan_access.hotspot_detected ? 'detected' : 'not detected'} · Keep-awake {data.lan_access.keep_awake ? 'active' : 'inactive'}</div>
            </div>
          </div>
          {data.lan_access.gateway_ready ? (
            <img src="/lan-access-qr.png" alt="QR code for the current CIAL LAN URL" className="h-32 w-32 rounded-xl border border-border bg-white p-2" />
          ) : null}
        </div>
      </article>

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
        <OverviewCard name="Backend" icon={Server} status={componentStatus(infrastructure.backend)} detail="API runtime" latency={infrastructure.backend.latency_ms} updated={updated} />
        <OverviewCard name="Database" icon={Database} status={componentStatus(infrastructure.postgresql)} detail="PostgreSQL metadata" latency={infrastructure.postgresql.latency_ms} updated={updated} />
        <OverviewCard name="Qdrant" icon={HardDrive} status={componentStatus(infrastructure.qdrant)} detail="Vector collection" latency={infrastructure.qdrant.latency_ms} updated={updated} />
        <OverviewCard name="Indexer" icon={Workflow} status={data.indexing.worker_stale ? 'yellow' : data.indexing.state === 'updating' ? 'blue' : 'green'} detail={data.indexing.worker_status} updated={updated} />
        <OverviewCard name="GPU" icon={Zap} status={data.gpu.cuda_available ? 'green' : 'yellow'} detail={data.gpu.device} updated={updated} />
        <OverviewCard name="Models" icon={Bot} status={data.models.ollama_available && data.models.embedding_model_ready ? 'green' : 'red'} detail={`${data.models.loaded_models.length} loaded`} updated={updated} />
      </div>

      <div className="grid gap-5 xl:grid-cols-[1.7fr_1fr]">
        <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between">
            <div><h2 className="font-semibold text-foreground">Live indexing pipeline</h2><p className="mt-1 text-xs text-muted-foreground">Durable job state and publication flow</p></div>
            <span className="text-xs font-medium text-muted-foreground">Generation {data.indexing.active_published_generation}</span>
          </div>
          <div className="mt-5"><Pipeline data={data} /></div>
          <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-4">
            <Metric label="Queue depth" value={data.indexing.queue_depth} />
            <Metric label="Completed" value={data.indexing.completed_jobs} />
            <Metric label="Throughput" value={formatNumber(data.indexing.throughput.documents_per_hour, '/hr')} />
            <Metric label="Failures" value={data.indexing.failed_jobs} />
          </div>
        </article>

        <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2"><Gauge size={18} className="text-primary" /><h2 className="font-semibold text-foreground">GPU monitoring</h2></div>
          <div className="mt-5 space-y-4">
            <div>
              <div className="flex justify-between text-xs"><span className="text-muted-foreground">Utilisation</span><span className="font-semibold">{formatNumber(data.gpu.utilization_percent, '%')}</span></div>
              <div className="mt-2 h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-[#4a8a3d]" style={{ width: `${Math.min(data.gpu.utilization_percent ?? 0, 100)}%` }} /></div>
            </div>
            <div>
              <div className="flex justify-between text-xs"><span className="text-muted-foreground">VRAM</span><span className="font-semibold">{data.gpu.memory_used_mb === null ? 'Unavailable' : `${data.gpu.memory_used_mb} / ${data.gpu.memory_total_mb} MB`}</span></div>
              <div className="mt-2 h-2 rounded-full bg-muted"><div className="h-2 rounded-full bg-info/100" style={{ width: `${data.gpu.memory_total_mb ? Math.min((data.gpu.memory_used_mb ?? 0) / data.gpu.memory_total_mb * 100, 100) : 0}%` }} /></div>
            </div>
            <div className="grid grid-cols-2 gap-2">
              <Metric label="GPU" value={data.gpu.device_name ?? 'Unavailable'} detail={data.gpu.driver_version ? `Driver ${data.gpu.driver_version}` : undefined} />
              <Metric label="Precision" value={data.gpu.precision} />
              <Metric label="Batch size" value={data.gpu.batch_size} />
              <Metric label="Free VRAM" value={data.gpu.memory_free_mb == null ? 'Unavailable' : `${data.gpu.memory_free_mb} MB`} detail={data.gpu.vram_target_ratio == null ? undefined : `${Math.round(data.gpu.vram_target_ratio * 100)}% indexer target`} />
              <Metric label="Device" value={data.gpu.embedding_device} />
              <Metric label="Configured device" value={data.gpu.embedding_device_configured ?? 'unknown'} />
              <Metric label="Actual model device" value={data.gpu.embedding_device_actual ?? 'unknown'} />
              <Metric label="Embedding model" value={data.gpu.embedding_model_status ?? 'unknown'} />
              <Metric label="Batch latency" value={formatNumber(data.gpu.embedding_batch?.duration_ms, ' ms')} />
            <Metric label="Query embedding" value={data.models.query_embedding_device ?? 'unknown'} detail={[data.models.query_embedding_dtype, data.models.query_embedding_model_state].filter(Boolean).join(' · ') || undefined} />
            <Metric label="Query policy" value={data.models.query_embedding_requested_device ?? 'unknown'} detail={[data.models.query_embedding_fallback_reason, `loads ${data.models.query_embedding_model_load_count ?? 0}`].filter(Boolean).join(' · ')} />
            <Metric label="Dense model" value={data.models.dense_model_status ?? 'unavailable'} />
            <Metric label="Reranker status" value={data.models.reranker_status ?? 'unavailable'} />
            <Metric label="Reranker device" value={data.models.reranker_device ?? 'Unavailable'} detail={[`requested ${data.models.reranker_requested_device ?? 'unknown'}`, data.models.reranker_dtype, data.models.reranker_fallback_reason, `loads ${data.models.reranker_model_load_count ?? 0}`].filter(Boolean).join(' · ')} />
            <Metric label="Device fallbacks" value={(data.models.device_fallback_count?.query_embedding ?? 0) + (data.models.device_fallback_count?.reranker ?? 0) + (data.models.device_fallback_count?.ollama ?? 0)} detail="query · reranker · Ollama" />
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
        <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2"><Cpu size={18} className="text-primary" /><h2 className="font-semibold">Worker monitoring</h2></div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <Metric label="CPU workers" value={data.cpu.extraction_workers} />
            <Metric label="GPU workers" value={data.indexing.active_workers} />
            <Metric label="OCR workers" value={data.cpu.ocr_workers} />
            <Metric label="Active tasks" value={data.cpu.current_tasks} />
          </div>
          <p className="mt-4 text-xs text-muted-foreground">Heartbeat {formatTime(data.indexing.worker_heartbeat_at)} · CPU {formatNumber(data.cpu.utilization_percent, '%')}</p>
        </article>

        <article className="rounded-2xl border border-border bg-card p-5 shadow-sm lg:col-span-2">
          <div className="flex items-center gap-2"><Activity size={18} className="text-primary" /><h2 className="font-semibold">Query pipeline</h2></div>
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
            <div className="mt-3 rounded-lg border border-warning/30 bg-warning/10 px-3 py-2 text-xs text-warning-foreground">
              Failed stage: <strong>{q.failed_stage}</strong>
              {q.timeout_reason ? ` · Timeout: ${q.timeout_reason}` : ''}
            </div>
          ) : null}
        </article>
      </div>

      <div className="grid gap-5 xl:grid-cols-[1fr_1.35fr]">
        <article className="rounded-2xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2"><Box size={18} className="text-primary" /><h2 className="font-semibold">Queue management</h2></div>
          <div className="mt-4 grid grid-cols-3 gap-2">
            <Metric label="Pending" value={data.indexing.pending_jobs} />
            <Metric label="Processing" value={data.indexing.active_jobs_count} />
            <Metric label="Failed" value={data.indexing.failed_jobs} />
          </div>
          <div className="mt-4 space-y-2">
            {Object.entries(data.indexing.priority_queues).map(([name, count]) => (
              <div key={name} className="flex items-center justify-between rounded-lg border border-border px-3 py-2 text-xs"><span className="font-medium text-foreground">{name.replaceAll('_', ' ')}</span><span className="font-bold text-foreground">{count}</span></div>
            ))}
            {!Object.keys(data.indexing.priority_queues).length ? <p className="py-3 text-center text-xs text-muted-foreground">No queued operations.</p> : null}
          </div>
        </article>

        <article className="overflow-hidden rounded-2xl border border-border bg-[#101814] text-slate-100 shadow-sm">
          <div className="flex items-center justify-between border-b border-white/10 px-5 py-4"><div className="flex items-center gap-2"><Activity size={17} className="text-emerald-400" /><h2 className="font-semibold">Live event stream</h2></div><span className="text-[11px] uppercase tracking-wider text-muted-foreground">{data.events.length} retained</span></div>
          <div className="max-h-[390px] overflow-y-auto">
            {data.events.map((event) => (
              <div key={event.id} className="grid grid-cols-[78px_10px_1fr] gap-3 border-b border-white/5 px-5 py-3 text-xs">
                <time className="font-mono text-muted-foreground">{formatTime(event.timestamp)}</time>
                <span className={`mt-1 h-2 w-2 rounded-full ${event.severity === 'error' ? 'bg-red-400' : event.severity === 'warning' ? 'bg-amber-400' : 'bg-emerald-400'}`} />
                <div><div className="font-mono text-emerald-300">{event.type}</div><div className="mt-1 text-muted-foreground/50">{event.message}</div></div>
              </div>
            ))}
            {!data.events.length ? <div className="px-5 py-10 text-center text-sm text-muted-foreground">Waiting for runtime state transitions…</div> : null}
          </div>
        </article>
      </div>
    </section>
  );
}
