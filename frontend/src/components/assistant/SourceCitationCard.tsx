import { useId, useState } from 'react';
import { ChevronDown, ExternalLink, FileText } from 'lucide-react';
import type { ChatSource } from '@/types/assistant';

interface SourceCitationCardProps {
  sources: ChatSource[];
  onOpenSource: (source: ChatSource) => void;
  includeExcerpts?: boolean;
}

export interface GroupedSource {
  key: string;
  documentTitle: string;
  sourceType: ChatSource['sourceType'];
  department?: string;
  pages: number[];
  citationIds: number[];
  sources: ChatSource[];
  excerpt?: string;
}

function normalizedSourceIdentity(source: ChatSource) {
  const stableId = (source.noteId || source.documentId)?.trim();
  if (stableId) return `id:${stableId}`;

  const fallback = (source.relativePath || source.documentTitle)
    .trim()
    .replace(/\\/g, '/')
    .replace(/\/+/g, '/')
    .toLocaleLowerCase();
  return `path:${fallback}`;
}

export function groupSourcesByDocument(sources: ChatSource[]): GroupedSource[] {
  const groups = new Map<string, GroupedSource>();

  for (const source of sources) {
    const key = normalizedSourceIdentity(source);
    const existing = groups.get(key);
    const page = typeof source.pageNumber === 'number' && source.pageNumber > 0
      ? Math.trunc(source.pageNumber)
      : typeof source.pageIndex === 'number' && source.pageIndex >= 0
        ? Math.trunc(source.pageIndex) + 1
        : undefined;

    if (!existing) {
      groups.set(key, {
        key,
        documentTitle: source.documentTitle,
        sourceType: source.sourceType,
        department: source.department,
        pages: page === undefined ? [] : [page],
        citationIds: [source.citationIndex],
        sources: [source],
        excerpt: source.previewText || source.highlightText || source.excerpt,
      });
      continue;
    }

    existing.sources.push(source);
    if (page !== undefined && !existing.pages.includes(page)) existing.pages.push(page);
    if (!existing.citationIds.includes(source.citationIndex)) existing.citationIds.push(source.citationIndex);
    if (!existing.excerpt) existing.excerpt = source.previewText || source.highlightText || source.excerpt;
  }

  return Array.from(groups.values());
}

function getSourceTypeStyles(sourceType: ChatSource['sourceType']) {
  if (sourceType === 'enterprise') return { label: 'Enterprise', className: 'ce-badge-accent' };
  if (sourceType === 'workspace') return { label: 'Workspace', className: 'border-[#c7d8e8] bg-[#eef6fc] text-[#346c96]' };
  return { label: 'Upload', className: 'border-[#efd8b5] bg-[#fff5e8] text-[#8a5208]' };
}

function summaryDocumentLabel(groups: GroupedSource[]) {
  if (groups.length === 1) return groups[0].documentTitle;
  return `${groups.length} sources`;
}

export default function SourceCitationCard({ sources, onOpenSource, includeExcerpts = true }: SourceCitationCardProps) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();
  const groups = groupSourcesByDocument(sources);

  if (sources.length === 0) return null;

  const pages = Array.from(new Set(groups.flatMap((group) => group.pages)));

  return (
    <div className="overflow-hidden rounded-[1.15rem] border border-[#dfe6dc] bg-white" data-testid="source-summary-accordion">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full min-w-0 items-center gap-3 px-3.5 py-3 text-left transition hover:bg-[#f8faf7] focus-visible:outline-2 focus-visible:outline-offset-[-2px] focus-visible:outline-ring sm:px-4"
        aria-expanded={expanded}
        aria-controls={contentId}
        data-testid="button-toggle-sources"
      >
        <FileText size={17} className="shrink-0 text-slate-500" />
        <span className="shrink-0 text-sm font-semibold text-foreground">
          {sources.length} source{sources.length === 1 ? '' : 's'}
        </span>
        <span aria-hidden="true" className="text-xs text-slate-400">•</span>
        <span className="min-w-0 truncate text-sm text-slate-600">{summaryDocumentLabel(groups)}</span>
        {pages.length > 0 ? (
          <>
            <span aria-hidden="true" className="hidden text-xs text-slate-400 sm:inline">•</span>
            <span className="hidden min-w-0 truncate text-sm text-slate-600 sm:inline">
              Pages {pages.join(', ')}
            </span>
          </>
        ) : null}
        <span className="ml-auto inline-flex shrink-0 items-center gap-1.5 text-sm font-semibold text-primary">
          <span className="hidden sm:inline">View sources</span>
          <ChevronDown size={16} className={`transition-transform ${expanded ? 'rotate-180' : ''}`} />
        </span>
      </button>

      <div id={contentId} hidden={!expanded} className="border-t border-[#e8ede6] bg-[#fbfcfa]" data-testid="grouped-source-list">
        {groups.map((group) => {
          const badge = getSourceTypeStyles(group.sourceType);
          return (
            <article key={group.key} className="border-b border-[#e8ede6] px-3.5 py-3 last:border-b-0 sm:px-4" data-testid="grouped-source-row">
              <div className="flex min-w-0 items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <h3 className="safe-text text-sm font-semibold text-foreground">{group.documentTitle}</h3>
                    <span className={`ce-badge ${badge.className}`}>{badge.label}</span>
                  </div>
                  <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-muted-foreground">
                    {group.pages.length > 0 ? <span>Pages {group.pages.join(', ')}</span> : null}
                    <span>Citations {group.citationIds.map((id) => `[${id}]`).join(', ')}</span>
                    {group.department ? <span>{group.department}</span> : null}
                  </div>
                  {includeExcerpts && group.excerpt ? <p className="safe-text mt-2 line-clamp-2 text-xs leading-5 text-slate-600">{group.excerpt}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={() => onOpenSource(group.sources[0])}
                  className="ce-action min-h-8 shrink-0 px-2.5 text-primary"
                  data-testid={`button-open-source-${group.sources[0].citationIndex}`}
                  aria-label={`Open ${group.documentTitle} at citation ${group.sources[0].citationIndex}`}
                >
                  <ExternalLink size={12} />
                  <span className="hidden sm:inline">Open</span>
                </button>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
