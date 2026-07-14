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

  if (sources.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-border bg-white p-3 text-xs text-muted-foreground" data-testid="source-citation-card-empty">
        No sources available for this response.
      </div>
    );
  }

  const visibleSources = expanded ? sources : sources.slice(0, 2);
  const hiddenCount = Math.max(0, sources.length - visibleSources.length);

  return (
    <div className="rounded-2xl bg-white/90 p-3 ring-1 ring-black/5" data-testid="source-citation-card">
      <div className="flex items-center justify-between gap-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">Sources</p>
        {sources.length > 2 ? (
          <button
            type="button"
            onClick={() => setExpanded((current) => !current)}
            className="inline-flex items-center gap-1 rounded-full border border-border bg-white px-2 py-1 text-[11px] font-semibold text-primary hover:bg-muted"
            data-testid="button-toggle-sources"
          >
            {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
            {expanded ? 'Collapse' : `Show ${hiddenCount} more`}
          </button>
        ) : null}
      </div>

      <div className="mt-3 space-y-2">
        {visibleSources.map((source) => {
          const badge = getSourceTypeStyles(source.sourceType);
          return (
            <article key={source.id} className="rounded-xl bg-[hsl(210_20%_98%)] p-3 ring-1 ring-black/5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="mb-1 flex flex-wrap items-center gap-2">
                    <span className="ce-badge ce-badge-accent">[{source.citationIndex}]</span>
                    <span className={`ce-badge ${badge.className}`}>{badge.label}</span>
                    {source.pageNumber !== undefined && source.pageNumber > 0 ? <span className="ce-meta-text font-semibold">p. {source.pageNumber}</span> : null}
                  </div>
                  <h3 className="safe-text text-sm font-semibold text-foreground">{source.documentTitle}</h3>
                  {source.department ? <p className="mt-1 text-[11px] text-muted-foreground">{source.department}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={() => onOpenSource(source)}
                  className="ce-action min-h-8 shrink-0 rounded-full px-3 text-primary"
                  data-testid={`button-open-source-${source.citationIndex}`}
                >
                  <ExternalLink size={12} />
                  Open
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
