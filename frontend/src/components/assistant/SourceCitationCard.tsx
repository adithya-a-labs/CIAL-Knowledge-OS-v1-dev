import { useState } from 'react';
import { ChevronDown, ChevronUp, ExternalLink } from 'lucide-react';
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
  const [expanded, setExpanded] = useState(false);
  const visibleSources = expanded ? sources : sources.slice(0, 3);
  const hiddenCount = Math.max(0, sources.length - visibleSources.length);

  if (sources.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-border bg-white p-3 text-xs text-muted-foreground" data-testid="source-citation-card-empty">
        No sources available for this response.
      </div>
    );
  }

  return (
    <div className="ce-card space-y-2 p-3" data-testid="source-citation-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs font-semibold text-foreground">Sources</p>
        {sources.length > 3 && (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="inline-flex items-center gap-1 rounded-lg border border-border bg-white px-2 py-1 text-[11px] font-semibold text-primary hover:bg-muted"
            data-testid="button-toggle-sources"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Show fewer' : `Show ${hiddenCount} more`}
          </button>
        )}
      </div>
      {visibleSources.map((source) => {
        const badge = getSourceTypeStyles(source.sourceType);
        return (
          <article key={source.id} className="rounded-lg border border-border bg-[hsl(210_20%_98%)] p-2.5">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <div className="mb-1 flex flex-wrap items-center gap-2">
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
                  {source.chunkId ? ` / ${source.chunkId}` : ''}
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
              <p className="safe-text mt-2 border-t border-border pt-2 text-[11px] leading-5 text-muted-foreground">
                {source.reason}
              </p>
            )}
          </article>
        );
      })}
    </div>
  );
}
