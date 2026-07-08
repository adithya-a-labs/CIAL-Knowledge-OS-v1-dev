import { ExternalLink } from 'lucide-react';
import type { ChatSource } from '@/types/assistant';

interface SourceCitationCardProps {
  sources: ChatSource[];
  onOpenSource: (source: ChatSource) => void;
}

function getSourceTypeStyles(sourceType: ChatSource['sourceType']) {
  if (sourceType === 'enterprise') {
    return { label: 'Enterprise', className: 'ce-badge-accent' };
  }
  if (sourceType === 'workspace') {
    return { label: 'Workspace', className: 'bg-[#eef6fc] text-[#346c96] border-[#c7d8e8]' };
  }
  return { label: 'Upload', className: 'bg-[#fff5e8] text-[#8a5208] border-[#efd8b5]' };
}

export default function SourceCitationCard({ sources, onOpenSource }: SourceCitationCardProps) {
  if (sources.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-white p-3 text-xs text-muted-foreground" data-testid="source-citation-card-empty">
        No sources available for this response.
      </div>
    );
  }

  return (
    <div className="ce-card space-y-2 p-3" data-testid="source-citation-card">
      <p className="text-xs font-semibold text-foreground">Sources</p>
      {sources.map((source) => {
        const badge = getSourceTypeStyles(source.sourceType);
        return (
          <article key={source.id} className="rounded-lg border border-border bg-[hsl(210_20%_98%)] p-3">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-1.5 flex flex-wrap items-center gap-2">
                  <span className="ce-badge ce-badge-accent">
                    [{source.citationIndex}]
                  </span>
                  <span className={`ce-badge ${badge.className}`}>
                    {badge.label}
                  </span>
                  {source.score !== undefined && (
                    <span className="ce-meta-text font-semibold">
                      {Math.round(source.score * 100)}% confidence
                    </span>
                  )}
                </div>
                <h3 className="safe-text text-xs font-semibold text-foreground">
                  {source.documentTitle}
                </h3>
                <p className="mt-1 text-[11px] text-muted-foreground">
                  {source.department ?? 'Department pending'}
                  {source.pageNumber ? ` / Page ${source.pageNumber}` : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onOpenSource(source)}
                className="ce-action shrink-0 text-primary"
                data-testid={`button-open-source-${source.citationIndex}`}
              >
                <ExternalLink size={12} />
                Open Source
              </button>
            </div>
            {source.reason && (
              <p className="safe-text mt-2 border-t border-border pt-2 text-[11px] leading-5 text-foreground">
                {source.reason}
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
