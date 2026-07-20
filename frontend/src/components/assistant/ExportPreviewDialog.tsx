import { useEffect, useRef, useState } from 'react';
import { Download, FileText, RefreshCcw, XCircle } from 'lucide-react';
import { cancelAssistantExport, fetchAssistantExportArtifact, getAssistantExport } from '@/api/client';
import type { AssistantExportFormat, AssistantExportJob } from '@/api/types';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { toast } from '@/hooks/use-toast';

interface Props { open: boolean; exportId: string | null; onOpenChange: (open: boolean) => void; onRegenerate: (format: AssistantExportFormat) => void; }
const terminal = new Set(['ready', 'failed', 'cancelled', 'expired']);
function fileSize(value?: number | null) { return value ? `${(value / 1024).toFixed(value > 1024 * 1024 ? 0 : 1)} KB` : ''; }

export default function ExportPreviewDialog({ open, exportId, onOpenChange, onRegenerate }: Props) {
  const [job, setJob] = useState<AssistantExportJob | null>(null); const [previewUrl, setPreviewUrl] = useState<string | null>(null); const [previewHtml, setPreviewHtml] = useState(''); const [downloading, setDownloading] = useState(false); const downloadLock = useRef(false);
  useEffect(() => {
    if (!open || !exportId) return; let active = true; const controller = new AbortController(); let timer: number | undefined;
    const poll = async () => { try { const next = await getAssistantExport(exportId, controller.signal); if (!active) return; setJob(next); if (!terminal.has(next.status)) timer = window.setTimeout(poll, 900); } catch (error) { if (active && !controller.signal.aborted) toast({ title: 'Export status unavailable', description: error instanceof Error ? error.message : 'Please retry.' }); } };
    void poll(); return () => { active = false; controller.abort(); if (timer) window.clearTimeout(timer); };
  }, [exportId, open]);
  useEffect(() => {
    if (!open || job?.status !== 'ready' || !job.preview?.url) return; const controller = new AbortController(); let objectUrl: string | null = null;
    void fetchAssistantExportArtifact(job.preview.url, controller.signal).then(async (response) => { if (job.preview?.type === 'pdf') { objectUrl = URL.createObjectURL(await response.blob()); setPreviewUrl(objectUrl); } else setPreviewHtml(await response.text()); }).catch((error) => { if (!controller.signal.aborted) toast({ title: 'Preview failed', description: error instanceof Error ? error.message : 'Preview could not be loaded.' }); });
    return () => { controller.abort(); if (objectUrl) URL.revokeObjectURL(objectUrl); setPreviewUrl(null); setPreviewHtml(''); };
  }, [job?.export_id, job?.status, job?.preview?.url, open]);
  const confirmDownload = async () => { if (!job?.download_url || downloadLock.current) return; downloadLock.current = true; setDownloading(true); try { const response = await fetchAssistantExportArtifact(job.download_url); const blob = await response.blob(); const url = URL.createObjectURL(blob); const anchor = document.createElement('a'); anchor.href = url; anchor.download = job.filename || `CIAL-Knowledge-OS.${job.format}`; anchor.click(); window.setTimeout(() => URL.revokeObjectURL(url), 1000); toast({ title: 'Download started' }); } catch (error) { toast({ title: 'Download failed', description: error instanceof Error ? error.message : 'Please retry.' }); } finally { setDownloading(false); downloadLock.current = false; } };
  const cancel = async () => { if (!exportId) return; try { await cancelAssistantExport(exportId); setJob((value) => value ? { ...value, status: 'cancelled', progress: { stage: 'cancelled', percent: value.progress.percent } } : value); } catch (error) { toast({ title: 'Cancel failed', description: error instanceof Error ? error.message : 'Please retry.' }); } };
  const ready = job?.status === 'ready';
  return <Dialog open={open} onOpenChange={onOpenChange}><DialogContent className="flex h-[90vh] max-w-5xl flex-col overflow-hidden p-0 sm:rounded-2xl">
    <DialogHeader className="border-b px-6 py-4"><div className="flex items-center gap-2"><FileText size={18}/><DialogTitle>{job?.filename || 'Preparing export'}</DialogTitle>{job && <span className="rounded-full bg-muted px-2 py-1 text-xs font-semibold uppercase">{job.format}</span>}</div><DialogDescription>{ready ? `${fileSize(job.file_size_bytes)} • Preview before confirming download` : 'Your conversation remains available while the backend renders this file.'}</DialogDescription></DialogHeader>
    <div className="min-h-0 flex-1 bg-slate-100 p-4">
      {!ready ? <div className="mx-auto mt-16 max-w-xl rounded-xl border bg-white p-6" aria-live="polite"><p className="text-sm font-semibold capitalize">{job?.progress.stage?.replaceAll('_',' ') || 'Queued'}</p><Progress className="mt-3" value={job?.progress.percent || 0}/><p className="mt-2 text-xs text-muted-foreground">{job?.progress.percent || 0}%</p>{job?.error && <div className="mt-4 rounded-md bg-red-50 p-3 text-sm text-red-700">{job.error.message}</div>}</div>
      : job.preview?.type === 'pdf' ? previewUrl ? <iframe className="h-full w-full rounded-lg border bg-white" title="PDF export preview" src={previewUrl}/> : <p className="p-8 text-center text-sm">Loading PDF preview…</p>
      : previewHtml ? <iframe className="h-full w-full rounded-lg border bg-white" sandbox="" title="DOCX Preview" srcDoc={previewHtml}/> : <p className="p-8 text-center text-sm">Loading DOCX preview…</p>}
    </div>
    <DialogFooter className="border-t px-6 py-4 sm:justify-between"><div>{job && !terminal.has(job.status) && <Button variant="outline" onClick={() => void cancel()}><XCircle size={14}/>Cancel</Button>}</div><div className="flex gap-2">{job && terminal.has(job.status) && job.status !== 'ready' && <Button variant="outline" onClick={() => onRegenerate(job.format)}><RefreshCcw size={14}/>Retry</Button>}{job && <Button variant="outline" onClick={() => onRegenerate(job.format === 'pdf' ? 'docx' : 'pdf')}>Switch to {job.format === 'pdf' ? 'DOCX' : 'PDF'}</Button>}<Button disabled={!ready || downloading} onClick={() => void confirmDownload()} aria-label="Confirm download"><Download size={14}/>{downloading ? 'Starting…' : 'Confirm Download'}</Button></div></DialogFooter>
  </DialogContent></Dialog>;
}
